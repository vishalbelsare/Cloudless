import datetime
import os
import re 
import sys
import pdb
from timeit import default_timer
#
import pylab
# import pandas # imported below only in case actually used
import matplotlib
import numpy as np
import scipy.special as ss
from numpy.random import RandomState
#
import DPMB_State as ds
# reload(ds) # reloading this causes an import loop of some sort
import pyx_functions as pf
reload(pf)


def transition_single_z(vector,random_state):
    cluster = vector.cluster
    state = cluster.state
    #
    vector.cluster.deassign_vector(vector)

    score_vec,draw = pf.calculate_cluster_conditional(
        state,vector,random_state.uniform())

    cluster = None
    if draw == len(state.cluster_list):
        cluster = state.generate_cluster_assignment(force_new = True)
    else:
        cluster = state.cluster_list[draw]
    cluster.assign_vector(vector)
    #
    return len(score_vec)-1

####################
# PROBABILITY FUNCTIONS

# deprecated : use pyx_functions optimized version instead
# def renormalize_and_sample(random_state,logpstar_vec):
#     p_vec = log_conditional_to_norm_prob(logpstar_vec)
#     randv = random_state.uniform()
#     for (i, p) in enumerate(p_vec):
#         if randv < p:
#             return i
#         else:
#             randv = randv - p

def log_conditional_to_norm_prob(logp_list):
    maxv = max(logp_list)
    scaled = [logpstar - maxv for logpstar in logp_list]
    logZ = reduce(np.logaddexp, scaled)
    logp_vec = [s - logZ for s in scaled]
    return np.exp(logp_vec)

def cluster_vector_joint(vector,cluster,state):
    alpha = state.alpha
    numVectors = len(state.get_all_vectors())
    if cluster is None or len(cluster.vector_list) == 0:
        alpha_term = np.log(alpha) - np.log(numVectors-1+alpha)
        data_term = state.num_cols*np.log(.5)
    else:
        boolIdx = np.array(vector.data,dtype=type(True))
        alpha_term = np.log(len(cluster.vector_list)) - np.log(numVectors-1+alpha)
        numerator1 = boolIdx * np.log(cluster.column_sums + state.betas)
        numerator2 = (~boolIdx) * np.log(len(cluster.vector_list) \
                                             - cluster.column_sums + state.betas)
        denominator = np.log(len(cluster.vector_list) + 2*state.betas)
        data_term = (numerator1 + numerator2 - denominator).sum()
    retVal = alpha_term + data_term
    return retVal,alpha_term,data_term

def create_alpha_lnPdf(state):
    # Note : this is extraneous work for relative probabilities
    #      : but necessary to determine true distribution probabilities
    lnProdGammas = sum([ss.gammaln(len(cluster.vector_list)) 
                        for cluster in state.cluster_list])

    lnPdf = lambda alpha: ss.gammaln(alpha) \
        + len(state.cluster_list)*np.log(alpha) \
        - ss.gammaln(alpha+len(state.vector_list)) \
        + lnProdGammas

    return lnPdf

def create_beta_lnPdf(state,col_idx):
    S_list = [cluster.column_sums[col_idx] for cluster in state.cluster_list]
    R_list = [len(cluster.vector_list) - cluster.column_sums[col_idx] \
                  for cluster in state.cluster_list]
    lnPdf = lambda beta_d: sum([ss.gammaln(2*beta_d) - 2*ss.gammaln(beta_d)
                                + ss.gammaln(S+beta_d) + ss.gammaln(R+beta_d)
                                - ss.gammaln(S+R+2*beta_d) 
                                for S,R in zip(S_list,R_list)])
    return lnPdf

def slice_sample_alpha(state,init=None):
    logprob = create_alpha_lnPdf(state)
    lower = state.alpha_min
    upper = state.alpha_max
    init = state.alpha if init is None else init
    slice = np.log(state.random_state.uniform()) + logprob(init)
    while True:
        a = state.random_state.uniform()*(upper-lower) + lower
        if slice < logprob(a):
            break;
        elif a < init:
            lower = a
        elif a > init:
            upper = a
        else:
            raise Exception('Slice sampler for alpha shrank to zero.')
    return a

def slice_sample_beta(state,col_idx,init=None):
    logprob = create_beta_lnPdf(state,col_idx)
    lower = state.beta_min
    upper = state.beta_max
    init = state.betas[col_idx] if init is None else init
    slice = np.log(state.random_state.uniform()) + logprob(init)
    while True:
        a = state.random_state.uniform()*(upper-lower) + lower
        if slice < logprob(a):
            break;
        elif a < init:
            lower = a
        elif a > init:
            upper = a
        else:
            raise Exception('Slice sampler for beta shrank to zero.')
    return a

def calc_alpha_conditional(state):
    original_alpha = state.alpha
    ##
    grid = state.get_alpha_grid()
    lnPdf = create_alpha_lnPdf(state)
    logp_list = []
    state.removeAlpha(lnPdf)
    base_score = state.score
    for test_alpha in grid:
        state.setAlpha(lnPdf,test_alpha)
        logp_list.append(state.score)
        state.removeAlpha(lnPdf)
    # Note: log gridding introduces (implicit) -log(x) prior
    #     : to get uniform prior, need to add back np.log(x)
    # logp_list += np.log(grid)
    
    state.setAlpha(lnPdf,original_alpha)
    return np.array(logp_list)-base_score,lnPdf,grid

def calc_beta_conditional(state,col_idx):
    original_beta = state.betas[col_idx]
    ##
    grid = state.get_beta_grid()
    lnPdf = create_beta_lnPdf(state,col_idx)
    logp_list = []
    state.removeBetaD(lnPdf,col_idx)
    base_score = state.score
    # Note: log gridding introduces (implicit) -log(x) prior
    #     : to get uniform prior, need to add back np.log(x)
    # prior_func = lambda x : +np.log(x) # uniform
    # prior_func = lambda x: -x          # unormalized gamma_func(k=1, theta=1)
    prior_func = None                    # retain implicit -log prior
    logp_arr = pf.calc_beta_conditional_helper(
        state,grid,col_idx,prior_func)
    logp_list = logp_arr.tolist()[0]
    ##
    state.setBetaD(lnPdf,col_idx,original_beta)
    return np.array(logp_list)-base_score,lnPdf,grid

# deprecated, use pyx_functions version
# def calculate_cluster_conditional(state,vector):
#     ##vector should be unassigned
#     conditionals = []
#     for cluster in state.cluster_list + [None]:
#         scoreDelta,alpha_term,data_term = cluster_vector_joint(
#             vector,cluster,state)
#         conditionals.append(scoreDelta + state.score)
#     return conditionals

def calculate_node_conditional(pstate,cluster):
    conditionals = pstate.mus
    return conditionals

def mle_alpha(clusters,points_per_cluster,max_alpha=100):
    mle = 1+np.argmax([ss.gammaln(alpha) + clusters*np.log(alpha) 
                       - ss.gammaln(clusters*points_per_cluster+alpha) 
                       for alpha in range(1,max_alpha)])
    return mle

def mhSample(initVal,nSamples,lnPdf,sampler,random_state):
    samples = [initVal]
    priorSample = initVal
    for counter in range(nSamples):
        unif = random_state.uniform()
        proposal = sampler(priorSample)
        thresh = np.exp(lnPdf(proposal) - lnPdf(priorSample)) ## presume symmetric
        if np.isfinite(thresh) and unif < min(1,thresh):
            samples.append(proposal)
        else:
            samples.append(priorSample)
        priorSample = samples[-1]
    return samples

####################
# UTILITY FUNCTIONS
def plot_data(data,fh=None,h_lines=None,title_str=None
              ,interpolation="nearest",**kwargs):
    if fh is None:
        fh = pylab.figure()
    pylab.imshow(data,interpolation=interpolation
                 ,cmap=matplotlib.cm.binary,**kwargs)
    if h_lines is not None:
        xlim = fh.get_axes()[0].get_xlim()
        pylab.hlines(h_lines-.5,*xlim,color="red",linewidth=3)
    if title_str is not None:
        pylab.title(title_str)
    return fh

def bar_helper(x,y,fh=None,v_line=None,title_str=None,which_id=0):
    if fh is None:
        fh = pylab.figure()
    pylab.bar(x,y,width=min(np.diff(x)))
    if v_line is not None:
        pylab.vlines(v_line,*fh.get_axes()[which_id].get_ylim()
                     ,color="red",linewidth=3)
    if title_str is not None:
        pylab.ylabel(title_str)
    return fh

def printTS(printStr):
    print datetime.datetime.now().strftime("%H:%M:%S") + " :: " + printStr
    sys.stdout.flush()

def listCount(listIn):
    return dict([(currValue,sum(np.array(listIn)==currValue)) 
                 for currValue in np.unique(listIn)])

def delta_since(start_dt):
    try: ##older datetime modules don't have .total_seconds()
        delta = (datetime.datetime.now()-start_dt).total_seconds()
    except Exception, e:
        delta = (datetime.datetime.now()-start_dt).seconds()
    return delta

def convert_rpa_representation(intarray):
    num_cols = 32*len(intarray[0])
    num_rows = len(intarray)
    data = np.ndarray((num_rows,num_cols),dtype=np.int32)
    for row_idx,row in enumerate(intarray):
        binary_rep = []
        for number in row:
            string_rep = bin(number)[2:].zfill(32)
            binary_rep.extend([int(value) for value in string_rep])
        data[row_idx] = binary_rep
    return data

def cifar_data_to_image(raw_data,filename=None):
    image_data = raw_data.reshape((3,32,32)).T
    fh = pylab.figure(figsize=(.5,.5))
    pylab.imshow(image_data,interpolation='nearest')
    if filename is not None:
        pylab.savefig(filename)
        pylab.close()
    return fh

def canonicalize_list(in_list):
    z_indices = []
    next_id = 0
    cluster_ids = {}
    for el in in_list:
        if el not in cluster_ids:
            cluster_ids[el] = next_id
            next_id += 1
        z_indices.append(cluster_ids[el])
    return z_indices,cluster_ids

def ensure_pandas():
    try:
        import pandas
    except ImportError:
        pandas_uri = 'http://pypi.python.org/packages/source/p/pandas/' + \
            'pandas-0.7.0rc1.tar.gz'
        system_str = ' '.join(['easy_install', pandas_uri])
        os.system(system_str)

def create_links(filename_or_series,source_dir,dest_dir):
    ensure_pandas()
    import pandas
    series = None
    if isinstance(filename_or_series,str):
        series = pandas.Series.from_csv(filename_or_series)
    elif isinstance(filename_or_series,pandas.Series):
        series = filename_or_series
    else:
        print "unknown type for filename_or_series!"
        return
    #
    if len(os.listdir(dest_dir)) != 0:
        print dest_dir + " not empty, empty and rerun"
        return
    #
    for vector_idx,cluster_idx in series.iteritems():
        cluster_dir = os.path.join(dest_dir,str(cluster_idx))
        if not os.path.isdir(cluster_dir):
            os.mkdir(cluster_dir)
        filename = ("%05d" % vector_idx) + ".png"
        from_file = os.path.join(source_dir,filename)
        to_file = os.path.join(cluster_dir,filename)
        #
        os.symlink(from_file,to_file)
    
####################
# SEED FUNCTIONS
def generate_random_state(seed):
    random_state = RandomState()
    if type(seed) == tuple:
        random_state.set_state(seed)
    elif type(seed) == int:
        random_state.seed(seed)
    elif type(seed) == RandomState:
        random_state = seed
    else:
        raise Exception("Bad argument to generate_random_state: " + str(seed)) 
    return random_state

####################
# ARI FUNCTIONS
def calc_ari(group_idx_list_1,group_idx_list_2):
    ##https://en.wikipedia.org/wiki/Rand_index#The_contingency_table
    ##presumes group_idx's are canonicaized
    Ns,As,Bs = gen_contingency_data(group_idx_list_1,group_idx_list_2)
    n_choose_2 = choose_2_sum(np.array([len(group_idx_list_1)]))
    cross_sums = choose_2_sum(Ns[Ns>1])
    a_sums = choose_2_sum(As)
    b_sums = choose_2_sum(Bs)
    return ((n_choose_2*cross_sums - a_sums*b_sums)
            /(.5*n_choose_2*(a_sums+b_sums) - a_sums*b_sums))

def choose_2_sum(x):
    return sum(x*(x-1)/2.0)
            
def count_dict_overlap(dict1,dict2):
    overlap = 0
    for key in dict1:
        if key in dict2:
            overlap += 1
    return overlap

def gen_contingency_data(group_idx_list_1,group_idx_list_2):
    group_idx_dict_1 = {}
    for list_idx,group_idx in enumerate(group_idx_list_1):
        group_idx_dict_1.setdefault(group_idx,{})[list_idx] = None
    group_idx_dict_2 = {}
    for list_idx,group_idx in enumerate(group_idx_list_2):
        group_idx_dict_2.setdefault(group_idx,{})[list_idx] = None
    ##
    Ns = np.ndarray((len(group_idx_dict_1.keys()),len(group_idx_dict_2.keys())))
    for key1,value1 in group_idx_dict_1.iteritems():
        for key2,value2 in group_idx_dict_2.iteritems():
            Ns[key1,key2] = count_dict_overlap(value1,value2)
    As = Ns.sum(axis=1)
    Bs = Ns.sum(axis=0)
    return Ns,As,Bs

class Timer(object):
    def __init__(self, task='action', verbose=False):
        self.task = task
        self.verbose = verbose
        self.timer = default_timer
    def __enter__(self):
        self.start = self.timer()
        return self
    def __exit__(self, *args):
        end = self.timer()
        self.elapsed_secs = end - self.start
        self.elapsed = self.elapsed_secs * 1000 # millisecs
        if self.verbose:
            print '%s took:\t% 7d ms' % (self.task, self.elapsed)

def get_max_iternum_filenames(dir_str):
    def get_max_iternum(file_tuples, basename):
        is_same_basename = lambda in_tuple: in_tuple[0] == basename
        basename_file_tuples = filter(is_same_basename, file_tuples)
        iternums = map(lambda x: int(x[1]), basename_file_tuples)
        return str(max(iternums))
    base_re = re.compile('^(summary_.*iternum)(\d+).pkl.gz$')
    base_re_func = lambda filename: base_re.match(filename)
    get_base_match = lambda in_list: filter(None, map(base_re_func, in_list))
    get_base_names = lambda in_list: \
        list(set(map(lambda x: x.groups()[0], get_base_match(in_list))))
    get_base_tuples = lambda in_list: \
        list(set(map(lambda x: x.groups(), get_base_match(in_list))))
    #
    all_files = os.listdir(dir_str)
    base_names = get_base_names(all_files)
    base_tuples = get_base_tuples(all_files)
    max_tuples = [
        (base_name, get_max_iternum(base_tuples, base_name))
        for base_name in base_names
        ]
    create_filename = lambda in_tuple: ''.join(in_tuple) + '.pkl.gz'
    filenames = map(create_filename, max_tuples)
    return filenames
