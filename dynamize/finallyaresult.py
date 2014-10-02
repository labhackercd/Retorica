# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import sys
import argparse
import unicodedata

import pandas
import pymongo
from clint.textui import puts


def transliterate_like_rails(string, replacement='?'):
    # XXX FIXME Is this enough like Rails' version?
    # Convert to ASCII and back to Unicode
    string = unicodedata.normalize('NFKD', string)
    return string.encode('ascii', 'replace').decode('utf-8')


def parameterize_like_rails(string, sep='-'):
    p = transliterate_like_rails(string)
    # Turn unwanted chars into the separator
    p = re.sub(r'[^a-z0-9\-_]+', sep, p)
    if sep:
        # No more than one separator in a row
        p = re.sub(r'(' + re.escape(sep) + '){2,}', sep, p)
        # Remove leading/trailing separators
        p = p.strip(sep)
    return p.lower()


def strip_deputy_name(name):
    # strip AKIRA OTSUBO (PRESIDENTE)
    name = re.sub(r'\s*\([^\)]+\)\s*$', '', name)

    # strip ALGUEM, ALGUMA COISA
    name = re.sub(r'\s*,.*$', '', name)

    # strip ALGUEM - PARLAMENTAR JOVEM
    # but don't touch AKIRA-TO
    name = re.sub(r'\s+-.*$', '', name)

    return name


def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('-H', '--host', type=unicode, default='localhost')
    parser.add_argument('-P', '--port', type=int, default=27017)
    parser.add_argument('-d', '--database', type=unicode, default='retorica_development')

    parser.add_argument('-t', '--title', type=unicode)

    parser.add_argument('result_file', type=argparse.FileType('r'))
    parser.add_argument('topics_file', type=argparse.FileType('r'))

    args = parser.parse_args(argv[1:])

    result = pandas.read_csv(args.result_file, index_col=0, encoding='utf-8')
    topics = pandas.read_csv(args.topics_file, header=None, index_col=0, encoding='utf-8')

    mongo = pymongo.MongoClient(args.host, args.port)
    database = getattr(mongo, args.database)

    dashboard_id = database.dashboards.insert({
        'slug': parameterize_like_rails(args.title),
        'title': args.title,
    })

    topic_idx_to_id = {}

    for row_idx in range(topics.shape[0]):
        row = topics.irow(row_idx)
        title = row.name
        observ = ignore = False

        if title.startswith('/'):
            title = title.strip('/')
            observ = True

        if title.startswith('__'):
            title = title.strip('__')
            ignore = True

        topic_id = database.topics.insert({
            'title': title,
            'observ': observ,
            'ignore': ignore,
            'words': [w for w in row],
            'dashboard_id': dashboard_id,
        })

        topic_idx_to_id[row_idx] = topic_id

    for row_idx in range(result.shape[0]):
        row = result.irow(row_idx)
        name = row.name
        emphasis = row[1]
        topic_idx = int(row[0])
        topic_id = topic_idx_to_id[topic_idx]

        stripped_name = strip_deputy_name(name)

        # XXX FIXME should be atomic!
        deputado = database.deputados.find_one({'nome_parlamentar': stripped_name})
        id_deputado = deputado['_id'] if deputado else None

        if id_deputado is None:
            # Try again with some transliteration
            # This happens to a guy named ANDRÉ -something
            stripped_name = transliterate_like_rails(stripped_name)
            id_deputado = deputado['_id'] if deputado else None

        database.emphases.insert({
            'name': name,
            'stripped_name': stripped_name,
            'emphasis': emphasis,
            'topic_id': topic_id,
            'deputado_id': id_deputado,
        })

if __name__ == '__main__':
    sys.exit(main(sys.argv) or 0)