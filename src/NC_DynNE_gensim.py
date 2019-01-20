'''
Dynamic RW-SGNS demo for Node Classification task
by Chengbin HOU & Han ZHANG
'''

import gensim
import logging
import time
import random
import pickle
import numpy as np
from downstream import ncClassifier
from sklearn.linear_model import LogisticRegression  # to do... try SVM...
from utils import *


def simulate_walks(nx_graph, num_walks, walk_length, restart_prob=None, affected_nodes=None):
     '''
     Repeatedly simulate random walks from each node
     '''
     G = nx_graph
     walks = []

     if affected_nodes == None: # simulate walks on every node in the graph [offline]
          nodes = list(G.nodes())
     else:                     # simulate walks on affected nodes [online]
          nodes = list(affected_nodes)

     if restart_prob == None: # naive random walk
          for walk_iter in range(num_walks):
               t1 = time.time()
               random.shuffle(nodes)
               for node in nodes:
                    walks.append(random_walk(nx_graph=G, start_node=node, walk_length=walk_length))
               t2 = time.time()
               # print(f'Walk iteration: {walk_iter+1}/{num_walks}; time cost: {(t2-t1):.2f}')
     else: # random walk with restart
          for walk_iter in range(num_walks):
               t1 = time.time()
               random.shuffle(nodes)
               for node in nodes:
                    walks.append(random_walk_restart(nx_graph=G, start_node=node, walk_length=walk_length, restart_prob=restart_prob))
               t2 = time.time()
               # print(f'Walk iteration: {walk_iter+1}/{num_walks}; time cost: {(t2-t1):.2f}')
     return walks


def random_walk(nx_graph, start_node, walk_length):
     '''
     Simulate a random walk starting from start node
     '''
     G = nx_graph
     walk = [start_node]

     while len(walk) < walk_length:
          cur = walk[-1]
          cur_nbrs = list(G.neighbors(cur))
          if len(cur_nbrs) > 0:
               walk.append(random.choice(cur_nbrs))
          else:
               break
     return walk

def random_walk_restart(nx_graph, start_node, walk_length, restart_prob):
     '''
     random walk with restart
     restart if p < restart_prob
     '''
     G = nx_graph
     walk = [start_node]

     while len(walk) < walk_length:
          p = random.uniform(0, 1)
          if p < restart_prob:
               cur = walk[0] # restart
               walk.append(cur)
          else:
               cur = walk[-1]
               cur_nbrs = list(G.neighbors(cur))
               if len(cur_nbrs) > 0:
                    walk.append(random.choice(cur_nbrs))
               else:
                    break
     return walk



if __name__ == '__main__':
     # logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
     community_dict = load_any_obj(path='../data/synthetic_LFR/LFR_community_dict.data') # ground truth

     is_dyn = False
     if not is_dyn:
          # ------ DeepWalk
          t1 = time.time()
          G_dynamic = load_dynamic_graphs('../data/synthetic_LFR/LFR_dynamic_graphs.data')

          # SGNS and suggested parameters to be tuned: size, window, negative, workers, seed
          # to tune other parameters, please read https://radimrehurek.com/gensim/models/word2vec.html#gensim.models.word2vec.Word2Vec

          for t in range(len(G_dynamic)):
               t3 = time.time()
               G0 = G_dynamic[t]
               w2v = gensim.models.Word2Vec(sentences=None, size=128, window=10, sg=1, hs=0, negative=5, ns_exponent=0.75,
                    alpha=0.025, min_alpha=0.0001, min_count=1, sample=0.001, iter=4, workers=8, seed=2019,
                    corpus_file=None, sorted_vocab=1, batch_words=10000, compute_loss=False,
                    max_vocab_size=None, max_final_vocab=None, trim_rule=None) # w2v constructor
               sentences = simulate_walks(nx_graph=G0, num_walks=10, walk_length=80, restart_prob=None)
               sentences = [[str(j) for j in i] for i in sentences]
               # print('sentences[:10]', sentences[:10]) # if set restart_prob=1, each sentence only contains itself
               w2v.build_vocab(sentences=sentences, update=False) # init traning, so update False
               w2v.train(sentences=sentences, total_examples=w2v.corpus_count, epochs=w2v.iter) # follow w2v constructor
               
               emb_dict = {} # nodeID: emb_vector
               for node in G_dynamic[t].nodes():
                    emb_dict[node] = w2v.wv[str(node)]

               # only select current available nodes for eval
               X = []
               Y = []
               for node in G_dynamic[t].nodes():
                    X.append(node)
                    Y.append(str(community_dict[node])) # label as str, otherwise, sklearn error
               print('Node Classification task, time step @: ', t)
               ds_task = ncClassifier(vectors=emb_dict, clf=LogisticRegression())
               ds_task.split_train_evaluate(X, Y, train_precent=0.5)

               t4 = time.time()
               print(f'current time step; time cost: {(t4-t3):.2f}s')
          t2 = time.time()
          print(f'Static NE -> all time steps; time cost: {(t2-t1):.2f}s')
     

     else: # 问题1）如何选择部分被影响点；2）如果对选中的点重采样；3）原来embedding是否要重置；4）如何更新，训练多少次等，越近越重要；5）多久重启训练问题
          # ------ DynDeepWalk
          t1 = time.time()
          G_dynamic = load_dynamic_graphs('../data/synthetic_LFR/LFR_dynamic_graphs.data')

          # SGNS and suggested parameters to be tuned: size, window, negative, workers, seed
          # to tune other parameters, please read https://radimrehurek.com/gensim/models/word2vec.html#gensim.models.word2vec.Word2Vec
          w2v = gensim.models.Word2Vec(sentences=None, size=128, window=10, sg=1, hs=0, negative=5, ns_exponent=0.75,
                              alpha=0.025, min_alpha=0.0001, min_count=1, sample=0.001, iter=4, workers=8, seed=2019,
                              corpus_file=None, sorted_vocab=1, batch_words=10000, compute_loss=False,
                              max_vocab_size=None, max_final_vocab=None, trim_rule=None) # w2v constructor

          for t in range(len(G_dynamic)):
               t3 = time.time()
               if t ==0:
                    G0 = G_dynamic[t]
                    sentences = simulate_walks(nx_graph=G0, num_walks=10, walk_length=80, restart_prob=None)
                    sentences = [[str(j) for j in i] for i in sentences]
                    # print('sentences[:10]', sentences[:10]) # if set restart_prob=1, each sentence only contains itself
                    w2v.build_vocab(sentences=sentences, update=False) # init traning, so update False
                    w2v.train(sentences=sentences, total_examples=w2v.corpus_count, epochs=w2v.iter) # follow w2v constructor
               else:
                    G0 = G_dynamic[t-1]
                    G1 = G_dynamic[t]
                    edge_add = edge_s1_minus_s0(s1=set(G1.edges()), s0=set(G0.edges()))
                    edge_del = edge_s1_minus_s0(s1=set(G0.edges()), s0=set(G1.edges()))
                    print('---> edges added: ', len(edge_add))
                    print('---> edges deleted: ', len(edge_del))
                    node_affected_by_edge_add = unique_nodes_from_edge_set(edge_add)
                    node_affected_by_edge_del = unique_nodes_from_edge_set(edge_del)
                    node_affected = node_affected_by_edge_add + node_affected_by_edge_del
                    print('---> nodes affected: ', len(node_affected))
                    # 新增的点？？？

                    sentences = simulate_walks(nx_graph=G1, num_walks=10, walk_length=80, restart_prob=None, affected_nodes=node_affected)
                    sentences = [[str(j) for j in i] for i in sentences]
                    # print('sentences[:10] updated', sentences[:10]) # if set restart_prob=1, each sentence only contains itself

                    w2v.build_vocab(sentences=sentences, update=True) # online update
                    w2v.train(sentences=sentences, total_examples=w2v.corpus_count, epochs=w2v.iter)

               # print('\n -----------------------------------------------')
               # print('wv for node 0 ', w2v.wv['0'])
               # print('similar_by_word for node 0', w2v.wv.similar_by_word('0'))
               # pca_vis(w2v)

               emb_dict = {} # nodeID: emb_vector
               for node in G_dynamic[t].nodes():
                    emb_dict[node] = w2v.wv[str(node)]
               '''
               # save emb as a dict
               time_step = str(t)
               path = '../output/emb_t' + time_step  
               save_emb(emb_dict=emb_dict, path=path)
               # lemb_dict = load_emb(path)
               '''
               # only select current available nodes for eval
               X = []
               Y = []
               for node in G_dynamic[t].nodes():
                    X.append(node)
                    Y.append(str(community_dict[node])) # label as str, otherwise, sklearn error
               print('Node Classification task, time step @: ', t)
               ds_task = ncClassifier(vectors=emb_dict, clf=LogisticRegression())  # use Logistic Regression as clf; we may choose SVM or more advanced ones
               ds_task.split_train_evaluate(X, Y, train_precent=0.5)

               t4 = time.time()
               print(f'current time step; time cost: {(t4-t3):.2f}s')
          t2 = time.time()
          print(f'Dynamic NE -> all time steps; time cost: {(t2-t1):.2f}s')