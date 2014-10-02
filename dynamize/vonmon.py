# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
import json
import os.path
import numpy
import argparse
import datetime
import itertools

import pandas
import pandas.rpy
import rpy2.robjects
from sklearn.feature_extraction.text import CountVectorizer
from clint.textui import indent, puts, progress, colored


# XXX BEHOLD DA' MONKEYPATCH BELOW!!!
#
# For whatever reason, `pandas.rpy.common` gives error when looking up for
# ordinary numpy types from its `VECTOR_TYPES` dict. Like it's looking up for
# `numpy.int64`, which is in the dict, but it's another instance of
# `numpy.int64`, so it's `id()` is different. Since I don't know why that is
# happening nor how to prevent it, I'll simply monkeypatch that dict and make
# it lookup types by name. It works for us.

class LookupByNameTypeDict(dict):
    def __init__(self, actual):
        super(LookupByNameTypeDict, self).__init__((str(t), v) for (t, v) in actual.items())

    def __getitem__(self, key):
        return super(LookupByNameTypeDict, self).__getitem__(str(key))

pandas.rpy.common.VECTOR_TYPES = LookupByNameTypeDict(pandas.rpy.common.VECTOR_TYPES)

# END OF MONKEYPATCH: We're *safe* now.


def shortnow(now=None):
    if now is None:
        now = datetime.datetime.now()
    return now.strftime(r'%Y%m%d%H%M%S')


def exp_agenda_vonmon(dtm, authors, ncats=70, verbose=False, kappa=400):
    """
    Call `exp.agenda.vonmon` through `rpy2`'s R interface.

    :param dtm: the Document Term Matrix
    :type dtm: pandas.DataFrame
    :param authors: the Authors matrix
    :type authors: pandas.DataFrame
    """
    THIS_DIR = os.path.abspath(os.path.dirname(__file__))

    # Now we prepare our data for `exp.agenda.vonmon`
    # 1) Convert the DTM to a R matrix
    # 2) Convert the authors matrix to a R matrix and sum it with 1 (because
    #    exp.agenda.vonmon uses 1-indexing, while the matrix is currently
    #    0-indexed)

    dtm = pandas.rpy.common.convert_to_r_matrix(dtm)
    authors = pandas.rpy.common.convert_to_r_matrix(authors.radd(1))

    rpy2.robjects.r('setwd("{0}")'.format(THIS_DIR))

    # Load `exp.agenda.vonmon` into the rpy2 environment
    rpy2.robjects.r("source('../r/ExpAgendVMVA.R')")

    exp_agenda_vonmon = rpy2.robjects.r('exp.agenda.vonmon')

    # Call it
    topics = exp_agenda_vonmon(term_doc=dtm, authors=authors, n_cats=ncats,
                               verbose=verbose, kappa=kappa)

    puts('Saving results...')

    rsave_rds = rpy2.robjects.r('saveRDS')
    rsave_rds(topics, file='topics_{0}.Rda'.format(shortnow()))

    return pandas.rpy.common.convert_robj(topics)


def build_authors_matrix(authors):
    start = 0

    names = []
    matrix = []

    while authors:
        cur = authors[0]
        count = authors.count(cur)

        matrix.append((start, start + count - 1))

        names.append(cur)

        start += count
        authors = authors[count:]

    return pandas.DataFrame(matrix, index=names)


class DocumentsFile(object):
    @classmethod
    def open(cls, filename):
        return cls(filename)

    def __init__(self, filename):
        self._fp = open(filename, 'r')
        self._line_count = sum(1 for _ in self._fp)
        self._fp.seek(0)

    def __len__(self):
        return self._line_count

    def __iter__(self):
        for line in self._fp:
            yield json.loads(line)

    def close(self):
        self._fp.close()


class Collector(list):
    def __init__(self, cb):
        self._callback = cb
        super(Collector, self).__init__()

    def collect(self, item):
        item, collected = self._callback(item)
        self.append(collected)
        return item


def eliminate_authors_with_only_one_speech(docs):
    cur = None
    prevdoc = None
    doccount = False

    #puts(str(len(next(docs))))
    #sys.exit(1)

    for author, doc in docs:
        if author != cur:
            cur = author
            prevdoc = doc
            doccount = False
        elif not doccount:
            yield author, prevdoc
            yield author, doc
            doccount = True
        else:
            yield author, doc


def mkdirp(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if not (exc.errno == errno.EEXIST and os.path.isdir(path)):
            raise


class WriteableDir(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        prospective_dir = values

        try:
            mkdirp(prospective_dir)
        except OSError as e:
            raise argparse.ArgumentError(prospective_dir, e.message)


def main(argv):

    parser = argparse.ArgumentParser()

    parser.add_argument('--mindf', type=float, default=1.0,
                        help='Minimum document frequency for cuts')
    parser.add_argument('--maxdf', type=float, default=1.0,
                        help='Maximum document frequency for cuts')
    parser.add_argument('--ncats', type=int, default=70,
                        help='Number of categories in the generated matrix')
    parser.add_argument('-o', '--output_directory', action=WriteableDir,
                        default=None, help=('Directory where the output data will be saved. '
                                            'If it doesnt exist well create it. '
                                            'Defaults to ./vonmon/<rightnow>.'))
    parser.add_argument('docsfile', type=unicode)

    args = parser.parse_args(argv[1:])

    # Sanitize arguments
    args.mindf = max(min(args.mindf, 1.0), 0.0)
    args.maxdf = max(min(args.maxdf, 1.0), 0.0)

    if args.maxdf == 1.0:
        args.maxdf = 1

    # Create dirs right now to avoid problems later!
    output_folder = args.output_directory
    if not output_folder:
        output_folder = os.path.abspath(os.path.join(
            os.getcwd(), 'vonmon',
            datetime.datetime.now().strftime('%Y-%m-%d_%H%M')))

    # Make sure it exists!
    mkdirp(output_folder)

    def outputpath(*args):
        return os.path.abspath(os.path.join(output_folder, *args))

    documents = DocumentsFile.open(args.docsfile)

    documents = progress.bar(documents)

    documents = eliminate_authors_with_only_one_speech(documents)

    def collect_author(item):
        author, document = item
        return document, author

    authors = Collector(collect_author)

    corpus = itertools.imap(authors.collect, documents)

    # Generate the Document Term Matrix
    puts("Building the DTM...")

    cv = CountVectorizer(min_df=args.mindf, max_df=args.maxdf)
    dtm = cv.fit_transform(corpus)

    authors = build_authors_matrix(authors)

    authors.to_csv('authors_{0}.csv'.format(shortnow()), encoding='utf-8')

    puts("DTM has {0} documents and {1} terms:".format(
        dtm.shape[0], dtm.shape[1],
    ))

    puts("")

    dtm = pandas.DataFrame(dtm.toarray(), columns=cv.get_feature_names())

    puts("Calling exp.agenda.vonmon through rpy2...")

    topics = exp_agenda_vonmon(dtm, authors, ncats=args.ncats, verbose=True)

    topics['thetas'].index = authors.index

    for key in topics.keys():
        filename = outputpath('{0}.csv'.format(key))
        topics[key].to_csv(filename, encoding='utf-8')

    thetas = topics['thetas']
    author_topics = thetas.idxmax(axis=1)

    # Create a proportion table with the results
    t = []
    for i in range(thetas.shape[0]):
        row = thetas.irow(i)
        t.append(row / numpy.sum(row))

    propthetas = pandas.DataFrame(t, index=thetas.index)

    result = []
    for i, topic_idx in enumerate(propthetas.idxmax(axis=1)):
        row = propthetas.irow(i)
        enfase = row[topic_idx]
        result.append((topic_idx, enfase))

    result = pandas.DataFrame(result, index=propthetas.index)
    result.to_csv(outputpath('result.csv'), encoding='utf-8')

    mus = topics['mus']

    topicwords = []
    for i in range(mus.shape[1]):
        words = mus.icol(i).sort(ascending=False, inplace=False)
        topicwords.append([w for (w, e) in words[:30].iteritems()])

    words = pandas.DataFrame(topicwords)
    words.to_csv(outputpath('words.csv'), header=False, index=False, encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main(sys.argv) or 0)