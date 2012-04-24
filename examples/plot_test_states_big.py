import matplotlib
matplotlib.use('Agg')
import DPMB_plotutils as dp
reload(dp)
import DPMB_State as ds
reload(ds)
import DPMB_helper_functions as hf
reload(hf)
import numpy as np
import matplotlib.pylab as pylab
##
import sys
if sys.platform == "win32":
    sys.path.append("c:/")
    
import Cloudless
reload(Cloudless)
import Cloudless.memo
reload(Cloudless.memo)


# block 2
# configure remote nodes
# TODO: Clean up naming of load balanced vs direct views
if sys.platform != "win32":
    Cloudless.base.remote_mode()
    Cloudless.base.remote_exec('import Cloudless.examples.DPMB_plotutils as dp')
    Cloudless.base.remote_exec('reload(dp)')
    Cloudless.base.remote_exec('import Cloudless.examples.DPMB_State as ds')
    Cloudless.base.remote_exec('reload(ds)')
    Cloudless.base.remote_exec('import Cloudless.examples.DPMB_helper_functions as hf')
    Cloudless.base.remote_exec('reload(hf)')
    Cloudless.base.remote_exec('import numpy as np')
    Cloudless.base.remote_exec('import matplotlib.pylab as pylab')
    
import Cloudless.examples.DPMB_plotutils as dp
reload(dp)
import Cloudless.examples.DPMB_State as ds
reload(ds)
import Cloudless.examples.DPMB_helper_functions as hf
reload(hf)
import numpy as np
import matplotlib.pylab as pylab


ALL_DATASET_SPECS = []

for num_clusters in [2,8]:##[2**(j+1) for j in [2]]:
    dataset_spec = {}
    dataset_spec["gen_seed"] = 0
    dataset_spec["num_cols"] = 8
    dataset_spec["num_rows"] = 64
    dataset_spec["gen_alpha"] = 1.0 #FIXME: could make it MLE alpha later
    dataset_spec["gen_betas"] = np.repeat(0.1, dataset_spec["num_cols"])
    dataset_spec["gen_z"] = ("balanced", num_clusters)
    dataset_spec["N_test"] = 5
    ALL_DATASET_SPECS.append(dataset_spec)

print "Generated " + str(len(ALL_DATASET_SPECS)) + " dataset specs!"

ALL_PROBLEMS = []
for dataset_spec in ALL_DATASET_SPECS:
    problem = hf.gen_problem(dataset_spec)
    ALL_PROBLEMS.append(problem)

print "Generated " + str(len(ALL_PROBLEMS)) + " problems!"

# now we have, in ALL_PROBLEMs, the dataset specs, along with training
# data, test data, the generating zs for the training data, and the average
# log probability of the test data under the generating model

# NOTE: Can clean up using itertools.product()
# http://docs.python.org/library/itertools.html#itertools.product
ALL_RUN_SPECS = []
num_iters = 3
count = 0
for problem in ALL_PROBLEMS:
    for infer_seed in range(1):
        for infer_init_alpha in [1.0]: #note: we're never trying sample-alpha-from-prior-for-init
            for infer_init_betas in [np.repeat(0.1, dataset_spec["num_cols"])]:
                for infer_do_alpha_inference in [True, False]:
                    for infer_do_betas_inference in [True, False]:
                        for infer_init_z in [1, "N", None]:
                            run_spec = {}
                            run_spec["num_iters"] = num_iters
                            run_spec["infer_seed"] = infer_seed
                            run_spec["infer_init_alpha"] = infer_init_alpha
                            run_spec["infer_init_betas"] = infer_init_betas
                            run_spec["infer_do_alpha_inference"] = infer_do_alpha_inference
                            run_spec["infer_do_betas_inference"] = infer_do_betas_inference
                            run_spec["infer_init_z"] = infer_init_z
                            run_spec["problem"] = problem
                            ALL_RUN_SPECS.append(run_spec)

print "Generated " + str(len(ALL_RUN_SPECS)) + " run specs!"
# until success:
#ALL_RUN_SPECS = ALL_RUN_SPECS[:1]

print "Running inference on " + str(len(ALL_RUN_SPECS)) + " problems..."

# now request the inference
memoized_infer = Cloudless.memo.AsyncMemoize("infer", ["run_spec"], hf.infer, override=True) #FIXME once we've debugged, we can eliminate this override

print "Created memoizer"

for run_spec in ALL_RUN_SPECS:
    memoized_infer(run_spec)

run_spec_filter = None ## lambda x: x["infer_init_z"] is None ## 

# now you can interactively call
for problem_idx,target_problem in enumerate(ALL_PROBLEMS):
    # FIXME : verify that the new gen_z works and the cluster_str below is correct
    cluster_str = "_clusters" + str(target_problem["dataset_spec"]["gen_z"][1]) ##
    col_str = "cols" + str(target_problem["dataset_spec"]["num_cols"])
    row_str = "rows" + str(target_problem["dataset_spec"]["num_rows"])
    cluster_str = "clusters" + str(cluster_str) ## 
    config_str = "_".join([col_str,row_str,cluster_str])    
    # hf.plot_measurement(memoized_infer, "num_clusters", target_problem,save_str="num_clusters_" + config_str + ".png"
    #                     ,title_str="num_clusters",ylabel_str="num_clusters")
    try:
        hf.plot_measurement(memoized_infer, ("ari", target_problem["zs"]), target_problem, run_spec_filter=run_spec_filter
                            ,save_str="ari_" + config_str + ".png",title_str=[config_str,"ari"],ylabel_str="ari"
                            ,legend_args={"ncol":2,"markerscale":2})
    except Exception, e:
        print e
        
#hf.plot_measurement(memoized_infer, "predictive", target_problem)

# with open("pickled_jobs.pkl","wb") as fh:
#     cPickle.dump({"memo":memoized_infer.memo,"ALL_RUN_SPECS":ALL_RUN_SPECS},fh)
