# -*- encoding : utf-8 -*-
class Deputado
  include Mongoid::Document
  include Mongoid::Attributes::Dynamic
  include Mongoid::Timestamps
  include Mongoid::Paperclip

  has_mongoid_attached_file :foto

  #field :_id, type: String
  field :id_cadastro, type: String
  field :situacao, type: String
  field :site_deputado, type: String
  field :nome_parlamentar, type: String
  field :sexo, type: String
  field :email, type: String

  has_and_belongs_to_many :partidos
  has_and_belongs_to_many :enfases
  has_and_belongs_to_many :unidade_federativa

  has_many :emphases, :class_name => 'Emphasis'

  validates_attachment :foto, content_type: { content_type: ["image/jpg", "image/jpeg", "image/png", "image/gif"] }

  def serializable_hash(options)
    # XXX FIXME DOESNT WORK :'(
    super({:include => {
      :foto_url => foto.url
    }}.merge(options))
  end
end
