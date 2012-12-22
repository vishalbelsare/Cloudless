#!python
import sys
import os
import datetime
from collections import namedtuple
#
# import Cloudless.examples.DPMB.optionally_use_agg as oua
# oua.optionally_use_agg()
# import pylab
import numpy as np
from collections import OrderedDict as od
#
import DPMB as dm
import helper_functions as hf
import pyx_functions as pf
##
import pdb

is_power_2 = lambda num: int(np.log2(num)) == np.log2(num)
is_crp_init_z = lambda init_z: \
    isinstance(init_z, str) and init_z.lower()=='crp'
cluster_suffstats_tuple = namedtuple(
    'cluster_suffstats_tuple',
    ' num_vectors column_sums '
    )
suffstats_tuple = namedtuple(
    'suffstats_tuple',
    ' num_vectors num_clusters list_of_cluster_suffstats list_of_x_indices '
    )

class DPMB_State():
    def __init__(self,gen_seed,num_cols,num_rows,init_alpha=None,init_betas=None
                 ,init_z=None,init_x=None,decanon_indices=None
                 ,alpha_min=.01,alpha_max=1.E6,beta_min=.01,beta_max=1.E6
                 ,grid_N=99
                 ,transitioner=None
                 ,data_dir=''
                 ):
        self.random_state = hf.generate_random_state(gen_seed)
        self.num_cols = num_cols
        self.alpha_min = alpha_min
        self.beta_min = beta_min
        self.alpha_max = alpha_max
        self.beta_max = beta_max
        self.grid_N = grid_N
        ##
        self.timing = {"alpha":0,"betas":0,"zs":0,"run_sum":0}
        self.verbose = False
        self.clip_beta = [1E-2,1E10]
        ##
        # note: no score modification here, because of uniform hyperpriors
        self.initialize_alpha(init_alpha)
        self.initialize_betas(init_betas)
        ##
        self.score = 0.0 #initially empty score
        self.cluster_list = [] #all the Clusters in the model
        self.vector_list = od() #contains all added (possibly unassigned) vectors, in order
        
        # now deal with init_z and init_x specs:
        if (init_z is None) and (init_x is not None):
            # can no longer initialize to cluster prior with specified data
            self.gibbs_type_init(num_rows, init_x, transitioner, data_dir)
        elif is_crp_init_z(init_z) and (init_x is not None):
            self.crp_type_init(init_x, data_dir)
        else:
            if isinstance(init_z, list) or isinstance(init_z,np.ndarray):
                init_z, canon_other = hf.canonicalize_list(init_z)
            self.non_gibbs_type_init(num_rows, init_z, init_x, decanon_indices)

    def crp_type_init(self, init_x, data_dir=''):
        num_rows = len(init_x)
        # create init_z from CRP
        crp_gen_seed = self.random_state.randint(sys.maxint)
        init_z, crp_counts = pf.sample_from_crp(
            alpha=self.alpha,
            random_seed=crp_gen_seed,
            num_draws=num_rows)
        init_z, canon_other = hf.canonicalize_list(init_z)
        # pass on to non_gibbs_type_init
        self.non_gibbs_type_init(num_rows, init_z, init_x)

    def gibbs_type_init(self, num_rows, init_x, transitioner=None, data_dir=''):

        # allocate each vector according to cluster_conditional
        # with the guts of hf.transition_single_z
        for R in xrange(num_rows):
            
            # dummmy cluster necessary for generation, auto-popped when deassigned
            cluster = self.generate_cluster_assignment(force_new=True)
            vector = self.generate_vector(data=init_x[R], cluster=cluster)
            cluster.deassign_vector(vector)

            unif = self.random_state.uniform()
            score_vec,draw = pf.calculate_cluster_conditional(
                self,vector,unif)
            cluster = None
            if draw == len(self.cluster_list):
                cluster = self.generate_cluster_assignment(force_new=True)
            else:
                cluster = self.cluster_list[draw]
            cluster.assign_vector(vector)

            # run inference on hypers
            if (R > 1) and is_power_2(R-1):
                if (transitioner is not None):
                    transitioner.state = self
                    transition_types = [
                        transitioner.transition_beta,
                        transitioner.transition_alpha
                        ]
                    for transition_type in \
                            self.random_state.permutation(transition_types):
                        transition_type()
                save_str = 'gibbs_init_after_numrows_' + str(R)
                save_str = os.path.join(data_dir, save_str)
                print save_str
                self.plot(save_str=save_str)

            # FIXME : Remove when done analyzing gibbs-init timing
            if R % 1000 == 0:
                print datetime.datetime.now(), R, len(self.cluster_list)
        # final hyper inference
        if (transitioner is not None):
            transitioner.state = self
            transition_types = [
                transitioner.transition_beta, transitioner.transition_alpha]
            for transition_type in \
                    self.random_state.permutation(transition_types):
                transition_type()
        # plot final state
        save_str = 'gibbs_init_after_numrows_' + str(R)
        save_str = os.path.join(data_dir, save_str)
        print save_str
        self.plot(save_str=save_str)

    def non_gibbs_type_init(self, num_rows, init_z, init_x,
                            decanon_indices=None):
        # init_z, cluster_ids = hf.canonicalize_list(init_z)

        for R in xrange(num_rows):
            cluster = None
            if init_z is None:
                cluster = self.generate_cluster_assignment()
            elif type(init_z) == int and init_z == 1: ##all in one cluster
                cluster = self.generate_cluster_assignment(force_last=True)
            elif init_z == "N": ##all apart
                cluster = self.generate_cluster_assignment(force_new=True)
            elif isinstance(init_z, tuple) and init_z[0] == "balanced":
                num_clusters = init_z[1]
                mod_val = num_rows / num_clusters
                if mod_val == 0 : 
                    raise Exception("num_rows not integer multiple of num_clusters")
                if R % mod_val == 0:
                    # create a new cluster
                    cluster = self.generate_cluster_assignment(force_new=True)
                else:
                    # use the last cluster
                    cluster = self.generate_cluster_assignment(force_last=True)
            elif isinstance(init_z, list) or isinstance(init_z,np.ndarray):
                if init_z[R] >= len(self.cluster_list):
                    cluster = self.generate_cluster_assignment(force_new=True)
                else:
                    cluster = self.cluster_list[init_z[R]]
            else:
                raise Exception("invalid init_z: " + str(init_z))

            # now we have the cluster. handle the data
            if init_x is None:
                vector = self.generate_vector(cluster = cluster)
            else:
                vector = self.generate_vector(data = init_x[R], cluster = cluster)

        if decanon_indices is not None:
            new_cluster_list = []
            for index in decanon_indices:
                new_cluster_list.append(self.cluster_list[index])
            self.cluster_list = new_cluster_list

    def initialize_alpha(self,init_alpha):
        if init_alpha is not None:
            self.alpha = init_alpha

        else:
            self.alpha = 10.0**self.random_state.uniform(
                np.log10(self.alpha_min),np.log10(self.alpha_max))
            
    def initialize_betas(self,init_betas):
        if init_betas is not None:
            self.betas = np.array(init_betas).copy()
        else:
            self.betas = 10.0**self.random_state.uniform(
                np.log10(self.beta_min),np.log10(self.beta_max),self.num_cols)
        pass
    
    def generate_cluster_assignment(self, force_last=False, force_new=False):
        if force_new:
            draw = len(self.cluster_list)
        elif force_last:
            draw = max(0,len(self.cluster_list) - 1)
        else:
            unnorm_vec = [len(cluster.vector_list) 
                          for cluster in self.cluster_list
                          ] + [self.alpha]
            draw = pf.renormalize_and_sample(
                #FIXME : should this be model's inference random_state
                #        after initial state generation?
                np.log(unnorm_vec),self.random_state.uniform())

        if draw == len(self.cluster_list):
            # create a new cluster and assign it
            cluster = Cluster(self)
            self.cluster_list.append(cluster)
            return cluster
        else:
            return self.cluster_list[draw]

    # sample a cluster from the CRP, possibly resulting in a new one being generated
    # if force_last is True, always returns the last generated cluster in the model
    # if force_new is True, always returns a new cluster
    # force_last and force_new can only both be True if there are no other clusters
    #
    # initializing all apart requires repeated calling with force_new=True
    # initializing all together requires repeated calling with force_last = True
    # initializing from the prior requires no arguments

    # Given:
    # data=None, cluster=None: sample cluster from CRP, sample data from predictive of that cluster.
    # data=None, cluster=c: sample data from c's predictive and incorporate it into c
    # data=dvec, cluster=c: incorporate dvec into c
    def generate_vector(self, data=None, cluster=None):
        if cluster is None:
            cluster = self.generate_cluster_assignment()

        vector = Vector(self.random_state, cluster, data) ## FIXME : does this need to be copied? np.array(data).copy())
        self.vector_list[vector] = None
        cluster.assign_vector(vector)
        return vector

    # remove the given vector from the model, destroying its cluster if needed
    def remove_vector(self, vector):
        # first we deassign it
        vector.cluster.deassign_vector(vector)
        vector.cluster = None ##deassign does this as well
        # now we remove it
        self.vector_list.pop(vector)

    def calculate_log_predictive(self, vector):
        assert vector.cluster is None,("Tried calculate_log_predictive on a" +
                                       " vector already in model. Not kosher!")
        clusters = list(self.cluster_list) + [None]
        log_joints = [pf.cluster_vector_joint(vector, cluster, self)[0]
                      for cluster in clusters]
        log_marginal_on_vector = reduce(np.logaddexp, log_joints)
        return log_marginal_on_vector
    
    def generate_and_score_test_set(self, N_test):
        xs = []
        lls = []
        #
        for i in xrange(N_test):
            test_vec = self.generate_vector()
            xs.append(test_vec.data)
            self.remove_vector(test_vec)
            lls.append(self.calculate_log_predictive(test_vec))
        #
        return xs,lls

    def score_test_set(self, test_xs):
        lls = []
        #
        for data in test_xs:
            # FIXME : could I just generate once, modify vector.data for each test_x and run calculate_log_predictive?
            test_vec = self.generate_vector(data=data)
            self.remove_vector(test_vec)
            lls.append(self.calculate_log_predictive(test_vec))
        #
        return lls
                                                            
    def clone(self):
        return DPMB_State(self.random_state, self.num_cols, len(self.vector_list), self.alpha, self.betas, self.getZIndices(), self.getXValues(),
                          self.alpha_min, self.alpha_max, self.beta_min, self.beta_max, self.grid_N)

    def get_flat_dictionary(self):
        ##init_* naming is used, but its not really init
        ##makes sense when needed for state creation
        ##but otherwise only if you want to resume inference
        return {"gen_seed":self.random_state, "num_cols":self.num_cols, "num_rows": len(self.vector_list), "alpha":self.alpha
                , "betas":self.betas.copy(), "zs":self.getZIndices(), "xs":self.getXValues()
                , "alpha_min":self.alpha_min, "alpha_max":self.alpha_max, "beta_min":self.beta_min, "beta_max":self.beta_max
                , "grid_N":self.grid_N} ## , "N_test":self.N_test} ## N_test isn't save, should it be?
            
    def get_alpha_grid(self):
        ##endpoint should be set by MLE of all data in its own cluster?
        grid = 10.0**np.linspace(np.log10(self.alpha_min),np.log10(self.alpha_max),self.grid_N) 
        return grid
    
    def get_beta_grid(self):
        grid = 10.0**np.linspace(np.log10(self.beta_min),np.log10(self.beta_max),self.grid_N)
        # grid = np.linspace(self.beta_min,self.beta_max,self.grid_N)
        return grid

    def get_all_vectors(self):
        return self.vector_list
            
    def get_timing(self):
        return self.timing.copy()

    def getZIndices(self):
        ##CANONICAL zs
        cluster_list = [v.cluster for v in self.get_all_vectors()]
        z_indices, cluster_ids = hf.canonicalize_list(cluster_list)
        return z_indices

    def get_decanonicalizing_indices(self):
        ##CANONICAL zs
        cluster_list = [v.cluster for v in self.get_all_vectors()]
        z_indices, cluster_ids = hf.canonicalize_list(cluster_list)

        decanon_indices = []
        for cluster in self.cluster_list:
            decanon_indices.append(cluster_ids[cluster])
        return decanon_indices

    def getXValues(self):
        data = []
        for vec in self.get_all_vectors():
            data.append(vec.data)
        return data

    def get_suffstats(self):
        list_of_cluster_suffstats = []
        list_of_x_indices = []
        for vector_idx, vector in enumerate(self.vector_list):
            vector.idx = vector_idx
        for cluster in self.cluster_list:
            x_indices = [vector.idx for vector in cluster.vector_list]
            cluster_suffstats = cluster_suffstats_tuple(
                len(cluster.vector_list), cluster.column_sums)
            #
            list_of_x_indices.append(x_indices)
            list_of_cluster_suffstats.append(cluster_suffstats)
        num_vectors = len(self.vector_list)
        num_clusters = len(self.cluster_list)
        suffstats = suffstats_tuple(num_vectors, num_clusters,
                                    list_of_cluster_suffstats,
                                    list_of_x_indices)
        return suffstats

    def removeAlpha(self,lnPdf):
        scoreDelta = lnPdf(self.alpha)
        self.score += -scoreDelta

    def setAlpha(self,lnPdf,alpha):
        scoreDelta = lnPdf(alpha)
        self.score += scoreDelta
        self.alpha = alpha

    def removeBetaD(self,lnPdf,colIdx):
        scoreDelta = lnPdf(self.betas[colIdx])
        self.score += -scoreDelta

    def setBetaD(self,lnPdf,colIdx,newBetaD):
        newBetaD = np.clip(newBetaD,self.clip_beta[0],self.clip_beta[1])
        scoreDelta = lnPdf(newBetaD)
        self.score += scoreDelta
        self.betas[colIdx] = newBetaD

    # directly modify score to avoid function overhead
    # def modifyScore(self,scoreDelta):
    #     self.score += scoreDelta

    def plot(self, which_plots=None, title_append=None,
             save_str=None, beta_idx=0, vector_idx=0,
             **kwargs):
        import pylab
        if len(self.cluster_list) == 0:
            if save_str is not None:
                pylab.figure()
                pylab.savefig(save_str)
            return
        if which_plots is None:
            which_plots = ["data","alpha","beta","cluster"]
        create_title = lambda title_str: title_str
        if title_append is not None:
            create_title = lambda title_str: ': '.join([title_str, title_append])
        fh = pylab.figure()
        num_rows = len(self.vector_list)

        no_data_plot_cutoff = 10000
        if 'just_data' in which_plots:
            if num_rows > no_data_plot_cutoff: return [None] * 5
            sort_by = self.getZIndices()
            argsort_indices = np.argsort(sort_by)
            data = np.array(self.getXValues())[argsort_indices]
            zs = np.array(self.getZIndices())[argsort_indices]
            h_lines = hf.zs_to_hlines(zs)
            title_str = create_title('Data')
            fh1 = hf.plot_data(
                data=data, fh=fh, h_lines=h_lines, title_str=title_str)
            if save_str is not None:
                pylab.savefig(save_str)
            return fh, fh1, None, None, None

        fh1 = None
        pylab.subplot(411)
        if "data" in which_plots and num_rows < no_data_plot_cutoff:
            sort_by = self.getZIndices()
            argsort_indices = np.argsort(sort_by)
            data = np.array(self.getXValues())[argsort_indices]
            zs = np.array(self.getZIndices())[argsort_indices]
            h_lines = hf.zs_to_hlines(zs)
            title_str = create_title('Data')
            fh1 = hf.plot_data(
                data=data, fh=fh, h_lines=h_lines, title_str=title_str)

        fh2 = None
        pylab.subplot(412)
        if "alpha" in which_plots or True:
            logp_list, lnPdf, grid = hf.calc_alpha_conditional(self)
            norm_prob = hf.log_conditional_to_norm_prob(np.array(logp_list))
            title_str = create_title('Alpha')
            log10_grid = np.log10(grid)
            v_line = np.log10(self.alpha)
            fh2 = hf.bar_helper(x=log10_grid, fh=fh, y=norm_prob, v_line=v_line,
                                title_str=title_str, which_id=1)

        fh3 = None
        pylab.subplot(413)
        if "beta" in which_plots:
            logp_list, lnPdf, grid = hf.calc_beta_conditional(self, beta_idx)
            norm_prob = hf.log_conditional_to_norm_prob(np.array(logp_list))
            title_str = create_title('Beta')
            log10_grid = np.log10(grid)
            v_line = np.log10(self.betas[beta_idx])
            fh3 = hf.bar_helper(x=log10_grid, y=norm_prob, fh=fh, v_line=v_line,
                                title_str=title_str, which_id=2)
            
        fh4 = None
        pylab.subplot(414)
        if ("cluster" in which_plots) and len(self.vector_list)>1:
            vector = list(self.vector_list)[vector_idx]
            cluster = vector.cluster
            ##ALWAYS GO THROUGH getZIndices
            vector_idx_in_global = list(self.vector_list).index(vector)
            cluster_idx = self.getZIndices()[vector_idx_in_global]

            # calculate the conditional
            cluster.deassign_vector(vector)
            score_vec = pf.calculate_cluster_conditional(self, vector, None)
            # score_vec is a list of scores, in the order of cluster_list.
            if cluster.state is None: ##handle singleton
                cluster = self.generate_cluster_assignment(self, force_new=True)
                cluster.assign_vector(vector)
            else:
                cluster.assign_vector(vector)                

            # sort score vec according to the order of the clusters from zindices
            next_id = 0
            cluster_ids = {}
            for v in self.get_all_vectors():
                if v.cluster not in cluster_ids:
                    cluster_ids[v.cluster] = next_id
                    next_id += 1

            # cluster_ids has a map from cluster references to z indices
            # but if a singleton was created and not chosen ("autopopped")
            # it is missing

            # move the scores according to the ordering we've found
            sorted_scores = [0 for x in xrange(len(score_vec))]
            for (i, cluster) in enumerate(self.cluster_list):
                sorted_scores[cluster_ids[cluster]] = score_vec[i]
            if len(vector.cluster.vector_list) > 1:
                # we need to put the singleton cluster's score at the end
                sorted_scores[-1] = score_vec[-1]
            norm_prob = hf.log_conditional_to_norm_prob(np.array(sorted_scores))
            
            title_str = create_title('Cluster\nconditional')
            try:
                x_vals = np.arange(len(norm_prob))-.5
                fh4 = hf.bar_helper(x=x_vals, y=norm_prob, fh=fh,
                                    v_line=cluster_idx, title_str=title_str,
                                    which_id=3)
            except Exception, e:
                print e 

        if save_str is not None:
            pylab.savefig(save_str)

        return fh,fh1,fh2,fh3,fh4


class Vector():
    def __init__(self,random_state,cluster,data=None):
        if cluster is None:
            raise Exception("creating a vector without a cluster")
        
        self.cluster = cluster
        if data is None:
            # reconstitute theta from the sufficient statistics for the cluster right now
            N_cluster = len(cluster.vector_list)
            num_heads_vec = cluster.column_sums
            binomial = random_state.binomial
            betas_vec = self.cluster.state.betas
            # thetas = (num_heads_vec + betas_vec) / (N_cluster + 2.0 * betas_vec)
            # self.data = np.array([random_state.binomial(1, theta) for theta in thetas])
            self.data = pf.create_data_array(
                N_cluster,num_heads_vec,betas_vec,binomial)
        else:
            self.data = data

class Cluster():
    def __init__(self, state):
        self.state = state
        self.column_sums = np.zeros(self.state.num_cols)
        self.vector_list = od()
        
    def count(self):
        return len(self.vector_list)

    def assign_vector(self,vector):
        scoreDelta,alpha_term,data_term = pf.cluster_vector_joint(vector,self,self.state)
        self.state.score += scoreDelta
        ##
        self.vector_list[vector] = None
        self.column_sums += vector.data
        vector.cluster = self
        
    def deassign_vector(self,vector):
        vector.cluster = None
        self.column_sums -= vector.data
        self.vector_list.pop(vector)
        ##
        scoreDelta,alpha_term,data_term = pf.cluster_vector_joint(vector,self,self.state)
        self.state.score += -scoreDelta
        if len(self.vector_list) == 0: # must remove (self) cluster if necessary
            self.state.cluster_list.remove(self)
            self.state = None
