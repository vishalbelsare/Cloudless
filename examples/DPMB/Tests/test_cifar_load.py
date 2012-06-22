#!python
import cPickle
import os
import datetime
from collections import Counter
#
import matplotlib
matplotlib.use('Agg')
import numpy as np
import pandas
from matplotlib.mlab import find
#
import Cloudless.examples.DPMB.settings as settings
reload(settings)
import Cloudless.examples.DPMB.remote_functions as rf
reload(rf)
import Cloudless.examples.DPMB.helper_functions as hf
reload(hf)
import Cloudless.examples.DPMB.DPMB_State as ds
reload(ds)
import Cloudless.examples.DPMB.DPMB as dm
reload(dm)
import Cloudless.examples.DPMB.PDPMB_State as pds
reload(pds)
import Cloudless.examples.DPMB.PDPMB as pdm
reload(pdm)

problem_file = os.path.join(settings.data_dir,settings.cifar_10_problem_file)
image_dir = os.path.join(settings.data_dir,settings.cifar_10_image_dir)
clustering_dir = os.path.join(settings.data_dir,settings.clustering_dir)
#
beta_d = 2.0
dataset_spec = {}
dataset_spec["pkl_file"] = problem_file
dataset_spec["gen_seed"] = 0
dataset_spec["num_cols"] = 256
dataset_spec["num_rows"] = 50000
dataset_spec["gen_alpha"] = 1.0
dataset_spec["gen_betas"] = np.repeat(beta_d, dataset_spec["num_cols"])
pkl_data = rf.unpickle(dataset_spec["pkl_file"])
dataset_spec["gen_z"],ids = hf.canonicalize_list(pkl_data["zs"])
init_x = pkl_data["xs"]
init_z = None # gibbs-type init
# init_z = dataset_spec["gen_z"] # ground truth init
#
problem = {}
problem["zs"] = dataset_spec["gen_z"]
problem["xs"] = init_x
problem["test_xs"] = pkl_data["test_xs"]
#
state = ds.DPMB_State(dataset_spec["gen_seed"],
                      dataset_spec["num_cols"],
                      dataset_spec["num_rows"],
                      init_alpha=dataset_spec["gen_alpha"],
                      init_betas=dataset_spec["gen_betas"],
                      init_z=dataset_spec["gen_z"],
                      init_x = init_x)

run_spec = {}
run_spec["dataset_spec"] = dataset_spec
run_spec["num_iters"] = 0
run_spec["infer_seed"] = 0
run_spec["infer_init_alpha"] = 1.0
run_spec["infer_init_betas"] = dataset_spec["gen_betas"].copy()
run_spec["infer_init_z"] = init_z
run_spec["infer_do_alpha_inference"] = True
run_spec["infer_do_betas_inference"] = True

verbose_state = run_spec.get("verbose_state",False)
decanon_indices = run_spec.get("decanon_indices",None)
num_nodes = run_spec.get("num_nodes",1)
hypers_every_N = run_spec.get("hypers_every_N",1)
time_seatbelt = run_spec.get("time_seatbelt",None)
ari_seatbelt = run_spec.get("ari_seatbelt",None)
#
if verbose_state:
    print "doing run: "
    for (k, v) in run_spec.items():
        if k.find("seed") != -1:
            print "   " + "hash(" + str(k) + ")" + " ---- " + str(hash(str(v)))
        else:
            print "   " + str(k) + " ---- " + str(v)
#
state_kwargs = {}
model_kwargs = {}
print "initializing"
if num_nodes == 1:
    state_type = ds.DPMB_State
    model_type = dm.DPMB
    state_kwargs = {"decanon_indices":decanon_indices}
else:
    state_type = pds.PDPMB_State
    model_type = pdm.PDPMB
    state_kwargs = {"num_nodes":num_nodes}
    model_kwargs = {"hypers_every_N":hypers_every_N}

init_start_ts = datetime.datetime.now()
inference_state = state_type(dataset_spec["gen_seed"],
                             dataset_spec["num_cols"],
                             dataset_spec["num_rows"],
                             init_alpha=run_spec["infer_init_alpha"],
                             init_betas=run_spec["infer_init_betas"],
                             init_z=run_spec["infer_init_z"],
                             init_x = problem["xs"],
                             **state_kwargs
                             )
init_delta_seconds = hf.delta_since(init_start_ts)

print "...initialized"
transitioner = model_type(
    inf_seed = run_spec["infer_seed"],
    state = inference_state,
    infer_alpha = run_spec["infer_do_alpha_inference"],
    infer_beta = run_spec["infer_do_betas_inference"],
    **model_kwargs
    )
#
summaries = []
summaries.append(
    transitioner.extract_state_summary(
        true_zs=problem["zs"]
        ,verbose_state=verbose_state
        ,test_xs=problem["test_xs"]))
summaries[-1]["timing"]["init"] = init_delta_seconds
#
print "saved initialization"
#
last_valid_zs = None
decanon_indices = None


def do_transitions(num_transitions):
    for i in xrange(num_transitions):
        transition_return = transitioner.transition(
            time_seatbelt=time_seatbelt
            ,ari_seatbelt=ari_seatbelt
            ,true_zs=problem["zs"]) # true_zs necessary for seatbelt 
        hf.printTS("finished doing iteration " + str(i))
        next_summary = transitioner.extract_state_summary(
            true_zs=problem["zs"]
            ,verbose_state=verbose_state
            ,test_xs=problem["test_xs"])
        time_elapsed_str = "%.1f" % next_summary["timing"].get("run_sum",0)
        hf.printTS("time elapsed: " + time_elapsed_str)
        if transition_return is not None:
            summaries[-1]["break"] = transition_return
            summaries[-1]["failed_info"] = next_summary
            break
        summaries.append(next_summary)
        hf.printTS("finished saving iteration " + str(i))
        if hasattr(transitioner.state,"getZIndices"):
            last_valid_zs = transitioner.state.getZIndices()
            decanon_indices = transitioner.state.get_decanonicalizing_indices()
    summaries[-1]["last_valid_zs"] = last_valid_zs
    summaries[-1]["decanon_indices"] = decanon_indices

def plot_full_state(which_betas=None):
    if which_betas is None:
        which_betas = xrange(len(inference_state.betas))
    transitioner.transition_beta()
    for beta_idx in which_betas:
        save_str = "cifar_init_state_beta" + str(beta_idx) + "_vector" + str(beta_idx)
        inference_state.plot(
            which_plots=["alpha","beta","cluster"],
            save_str=save_str,
            show=False,
            beta_idx=beta_idx,
            vector_idx=beta_idx
            )

def write_state(filename,data=None):
    if data is None:
        data = summaries[-1]['last_valid_zs']
    pandas.DataFrame(data).to_csv(filename)

def create_links(filename_or_series,source_dir,dest_dir):
    series = None
    if isinstance(filename_or_series,str):
        series = pandas.DataFrame.from_csv(filename)["0"]
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


def do_stats():
    print "scan times: " + str(
        np.diff([summary["timing"]["run_sum"] for summary in summaries]))
    print "num clusters: " + str(summaries[-1]['num_clusters'])
    print "cluster counts: " + str(summaries[-1]['cluster_counts'])
    print "mean test_ll: " + str(np.mean(summaries[-1]['test_lls']))
    
def link_helper():
    series = pandas.Series(summaries[-1]["last_valid_zs"])
    create_links(series,image_dir,clustering_dir)

def write_helper():
    filename = "cifar_10_state_iter"+str(transitioner.transition_count)+".csv"
    write_state(filename,summaries[-1]["last_valid_zs"])

if False:
    do_transitions(1)
    do_stats()
    plot_full_state(range(10))
    link_helper()