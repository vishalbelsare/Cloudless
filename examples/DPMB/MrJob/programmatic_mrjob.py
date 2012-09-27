#!python
import os
from collections import namedtuple
import hashlib
import argparse
#
import matplotlib
matplotlib.use('Agg')
#
import Cloudless.examples.DPMB.settings as S
reload(S)
import Cloudless.examples.DPMB.MrJob.seed_inferer as si
reload(si)
import Cloudless.examples.DPMB.Tests.create_synthetic_data as csd
reload(csd)
import Cloudless.examples.DPMB.MrJob.consolidate_summaries as cs
reload(cs)


# parse some arguments
parser_description = 'programmatically run mrjob on a synthetic problem'
parser = argparse.ArgumentParser(description=parser_description)
# problem settings
parser.add_argument('gen_seed', type=int)
parser.add_argument('num_rows', type=int)
parser.add_argument('num_cols', type=int)
parser.add_argument('num_clusters', type=int)
parser.add_argument('beta_d', type=float)
# inference settings
parser.add_argument('num_iters', type=int)
parser.add_argument('num_nodes_list', nargs='+', type=int)
#
args = parser.parse_args()

# problem settings
gen_seed = args.gen_seed
num_rows = args.num_rows
num_cols = args.num_cols
num_clusters = args.num_clusters
beta_d = args.beta_d
#
# inference settings
num_iters = args.num_iters
num_nodes_list = args.num_nodes_list
#
# non passable settings
base_dir = S.data_dir
seed_filename = 'seed_list.txt'
image_save_str = 'mrjob_problem_gen_state'
gibbs_init_filename = 'gibbs_init.pkl.gz'
data_dir_prefix = 'programmatic_mrjob_'
parameters_filename = 'run_parameters.txt'

# determine data dir
get_hexdigest = lambda variable: \
    hashlib.sha224(str(variable)).hexdigest()[:10]
hex_digest = get_hexdigest(vars(args))
data_dir = data_dir_prefix + hex_digest
data_dir = os.path.join(base_dir, data_dir)
try:
    os.makedirs(data_dir)
except OSError, ose:
    pass

# create the problem and seed file
problem, problem_filename = csd.pkl_mrjob_problem(
    gen_seed, num_rows, num_cols, num_clusters, beta_d,
    image_save_str=image_save_str, dir=data_dir)
seed_full_filename = os.path.join(data_dir, seed_filename)
os.system('printf "0\n" > ' + seed_full_filename)

# helper functions
create_args = lambda num_iters, num_nodes: [
    '--jobconf', 'mapred.map.tasks=' + str(num_nodes),
    # may need to specify mapred.map.tasks greater than num_nodes
    '--num-iters', str(num_iters),
    '--num-nodes', str(num_nodes),
    '--problem-file', problem_filename,
    '--data_dir', data_dir,
    seed_full_filename,
    ]

# gibbs init to be used by all subsequent inference
# iters=0, nodes=1
gibbs_init_args = ['--gibbs-init-file', gibbs_init_filename]
gibbs_init_args.extend(create_args(0, 1))
mr_job = si.MRSeedInferer(args=gibbs_init_args)
# mr_job.init(0,0).next()
with mr_job.make_runner() as runner:
    runner.run()

# now run for each num_nodes
for num_nodes in num_nodes_list:
    print 'starting num_nodes = ' + str(num_nodes)
    infer_args = ['--resume-file', gibbs_init_filename]
    infer_args.extend(create_args(num_iters, num_nodes))
    mr_job = si.MRSeedInferer(args=infer_args)
    with mr_job.make_runner() as runner:
        runner.run()

summaries_dict, numnodes1_seed1 = cs.read_summaries([data_dir])
cs.plot_summaries(summaries_dict, plot_dir=data_dir)

# create dir for results
this_file = __file__
data_files = os.path.join(data_dir, '*{png,txt,pkl.gz}')
#
system_str = ' '.join(['cp', this_file, data_dir])
os.system(system_str)

# system_str = ' '.join(['mv', data_files, data_dir])
# system_str = ' '.join(['echo', system_str, '| bash'])
# os.system(system_str)