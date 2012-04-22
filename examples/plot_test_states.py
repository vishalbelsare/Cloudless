import DPMB_plotutils as dp
reload(dp)
import DPMB_helper_functions as hf
reload(hf)
import DPMB_State as ds
reload(ds)
import numpy as np
import matplotlib.pylab as pylab


ALL_DATASET_SPECS = []

for num_clusters in [2**(j+1) for j in range(3)]:
    dataset_spec = {}
    dataset_spec["gen_seed"] = 0
    dataset_spec["num_cols"] = 8
    dataset_spec["num_rows"] = 8
    dataset_spec["gen_alpha"] = 1.0 #FIXME: could make it MLE alpha later
    dataset_spec["gen_betas"] = np.repeat(0.01, dataset_spec["num_cols"])
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
ALL_RUN_SPECS = []
num_iters = 20
count = 0
for problem in ALL_PROBLEMS:
    for infer_seed in range(5):
        for infer_init_alpha in [1.0]: #note: we're never trying sample-alpha-from-prior-for-init
            for infer_init_betas in [np.repeat(0.1, dataset_spec["num_cols"])]:
                for infer_do_alpha_inference in [True, False]:
                    for infer_do_betas_inference in [True, False]:
                        for infer_init_z in [1, "N", "P"]:
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
ALL_RUN_SPECS = ALL_RUN_SPECS[:1]

print "Running inference on " + str(len(ALL_RUN_SPECS)) + " problems..."

# now request the inference
import sys
sys.path.append("c://")
import Cloudless
reload(Cloudless)
import Cloudless.memo
reload(Cloudless.memo)

memoized_infer = Cloudless.memo.AsyncMemoize("infer", ["run_spec"], hf.infer, override=True) #FIXME once we've debugged, we can eliminate this override

print "Created memoizer"

for run_spec in ALL_RUN_SPECS:
    memoized_infer(run_spec)

# now you can interactively call
target_problem = ALL_PROBLEMS[0]
hf.plot_measurement(memoized_infer, "num_clusters", target_problem)
#hf.plot_measurement(memoized_infer, ("ari", target_problem["zs"]), target_problem)
#hf.plot_measurement(memoized_infer, "predictive", target_problem)