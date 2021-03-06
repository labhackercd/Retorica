#"<--- Copyright 2013 de Ret�rica/Davi Moreira, Luis Carli e Manoel Galdino 
# Este arquivo � parte do programa Retorica. 
# O Retorica � um software livre; voc� pode redistribu�-lo e/ou modific�-lo dentro 
# dos termos da [GNU General Public License OU GNU Affero General Public License] 
# como publicada pela Funda��o do Software Livre (FSF); na vers�o 3 da Licen�a. 
# Este programa � distribu�do na esperan�a que possa ser �til, mas SEM NENHUMA GARANTIA; 
# sem uma garantia impl�cita de ADEQUA��O a qualquer MERCADO ou APLICA��O EM PARTICULAR. 
# Veja a licen�a para maiores detalhes. Voc� deve ter recebido uma c�pia da 
# [GNU General Public License OU GNU Affero General Public License], sob o t�tulo "LICENCA.txt"

# The code ExpAgendVMVA.R was kindly provided by Professor Justin Grimmer, Stanford University, 
# on september 2013.
#  If you use it, please, cite his paper.
#  +----------------------------------------------------------------+
#  |  Citations:                                                    |
#  |    Grimmer, Justin. "A Bayesian hierarchical topic model for   |
#  |    political texts: Measuring expressed agendas in Senate      |
#  |    press releases." Political Analysis 18.1 (2010): 1-35.      |
#  +----------------------------------------------------------------+

# pacotes
if(require(rjson) == F) {install.packages("rjson"); require(rjson)}

# load de arquivos -------------------------------------------------------------

setwd('Diretorio')

load("DTM.RData") # Document Term Matrix
load("Autor_Matrix.RData") # Author Matrix
load("Info.RData")

source('ExpAgendVMVA.R')

topics <- exp.agenda.vonmon(term.doc = as.matrix(dtm), authors = autorMatrix, 
                          n.cats = 70, 
                          verbose = T, kappa = 400)

# Definindo topicos de cada autor e arquivo final
autorTopicOne <- NULL
for( i in 1:dim(topics[[1]])[1]){
  autorTopicOne[i] <- which.max(topics[[1]][i,])
}
autorTopicPerc <- prop.table(topics[[1]], 1) #  compute the proportion of documents from each author to each topic

autorTopicOne <- as.data.frame(autorTopicOne)

for( i in 1:nrow(autorTopicOne)){
  autorTopicOne$enfase[i] <- autorTopicPerc[i,which.max(autorTopicPerc[i,])]
}

json_file <- "https://github.com/Demoulidor/Dados/tree/master/deputadosFederais/deputados.json"
json_data <- fromJSON(paste(readLines(json_file), collapse=""))

df <- data.frame(nome=json_data[[1]][[1]]$nome, 
                 url=json_data[[1]][[1]]$url, 
                 foto=gsub("full\\/", "", json_data[[1]][[1]]$images[[1]]$path),
                 email=gsub("mailto:", "", json_data[[1]][[1]]$email), 
                 id=json_data[[1]][[1]]$id_dep)

for ( i in 2:length(json_data[[1]])) {
  df <- rbind(df, data.frame(nome=json_data[[1]][[i]]$nome, 
                             url=json_data[[1]][[i]]$url, 
                             foto=gsub("full\\/", "", json_data[[1]][[i]]$images[[1]]$path),
                             email=gsub("mailto:", "", json_data[[1]][[i]]$email), 
                             id=json_data[[1]][[i]]$id_dep))
}


autorTopicOne$uf <- infoPeqExpArrumado$uf[!duplicated(infoPeqExpArrumado$autor)]
autorTopicOne$partido <- infoPeqExpArrumado$partido[!duplicated(infoPeqExpArrumado$autor)]

autorTopicOne$autor <- unique(infoPeqExpArrumado$autor)

head(autorTopicOne)

autorTopicVis <- merge(autorTopicOne, df, by.x="autor", by.y="nome", all.x=T)

# arrumando sites dos deputados
autorTopicVis$url <- gsub("http:\\/\\/", "http:\\/\\/www.", autorTopicVis$url)

# rotulando topicos
rotulos <- read.table('20131031_rotulos1.txt', sep = "\t", header = T)

autorTopicVis <-  merge(autorTopicVis, rotulos[,c('topico','rotulo')], by.x='autorTopicOne', by.y='topico', all.x=T)

write.table(autorTopicVis , file="20131031_autorTopicVis_70.csv", sep=",", row.names=T)