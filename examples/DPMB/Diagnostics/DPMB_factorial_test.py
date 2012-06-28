#!python
import os
import Cloudless.examples.DPMB.remote_functions as rf
reload(rf)
import Cloudless.examples.DPMB.helper_functions as hf
reload(hf)
import Cloudless.examples.DPMB.DPMB as dm
reload(dm)
import Cloudless.examples.DPMB.DPMB_State as ds
reload(ds)
import Cloudless.examples.DPMB.settings as settings
reload(settings)

data_dict = rf.unpickle(os.path.join(settings.data_dir,'factorial_problem.pkl.gz'))
data = data_dict['data']
inverse_permutation_indices_list = data_dict['inverse_permutation_indices_list']
zs_to_permute = data_dict['zs_to_permute']
num_rows = data.shape[0]
num_cols = data.shape[1]

gen_seed = 0
inf_seed = 0

state = ds.DPMB_State(
    gen_seed=0,
    num_cols=num_cols,
    num_rows=num_rows,
    init_x=data)

transitioner = dm.DPMB(
    inf_seed=inf_seed,
    state=state,
    infer_alpha=True,
    infer_beta=True)

summaries = []
next_summary = transitioner.extract_state_summary()
#
ari_list = []
for inverse_permutation_indices in inverse_permutation_indices_list:
    ari_list.append(hf.calc_ari(
        state.getZIndices(),zs_to_permute[inverse_permutation_indices]))
next_summary['ari_list'] = ari_list
summaries.append(next_summary)

for i in range(100):
    transitioner.transition()
    next_summary = transitioner.extract_state_summary()
    ari_list = []
    for inverse_permutation_indices in inverse_permutation_indices_list:
        ari_list.append(hf.calc_ari(
            state.getZIndices(),zs_to_permute[inverse_permutation_indices]))
    next_summary['ari_list'] = ari_list
    summaries.append(next_summary)

ari_mat = numpy.array([summary['ari_list'] for summary in summaries])
import pylab
pylab.plot(ari_mat)
