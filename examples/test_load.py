import DPMB_plotutils as dp
reload(dp)
import DPMB_helper_functions as hf
reload(hf)
import DPMB_State as ds
reload(ds)
import numpy as np
import matplotlib.pylab as pylab

import sys
sys.path.append("c://")
import Cloudless
reload(Cloudless)
import Cloudless.memo
reload(Cloudless.memo)

if "memoized_infer" not in locals():
    memoized_infer = Cloudless.memo.AsyncMemoize("infer", ["run_spec"], hf.infer, override=True) #FIXME once we've debugged, we can eliminate this override
    ALL_RUN_SPECS = hf.unpickle_asyncmemoize(memoized_infer,"pickled_jobs.pkl")

run_spec_filter = lambda x: x["infer_init_z"] == 1 
##hf.try_plots(memoized_infer,which_measurements=["mean_beta","ari","alpha"],run_spec_filter=run_spec_filter)
hf.try_plots(memoized_infer,which_measurements=["mean_beta"],run_spec_filter=run_spec_filter)
