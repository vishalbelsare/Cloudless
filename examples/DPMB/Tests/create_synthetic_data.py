#!python
import argparse
import sys
import os
#
import matplotlib
matplotlib.use('Agg')
import numpy
import pylab
#
import Cloudless.examples.DPMB.DPMB_State as ds
reload(ds)
import Cloudless.examples.DPMB.remote_functions as rf
reload(rf)
import Cloudless.examples.DPMB.helper_functions as hf
reload(hf)
import Cloudless.examples.DPMB.settings as S
reload(S)


def gen_data(gen_seed,num_clusters,num_cols,num_rows,beta_d):
    state = ds.DPMB_State(
        gen_seed=gen_seed,
        num_cols=num_cols,
        num_rows=num_rows,
        init_z=('balanced',num_clusters),
        init_betas = numpy.repeat(beta_d,num_cols)
    )
    return state.getXValues()

def gen_hierarchical_data(gen_seed,num_clusters,num_cols,num_rows,num_splits,
                          beta_d,
                          plot=False,image_save_str=None):
    numpy.random.seed(gen_seed)
    cols_per_split = num_cols/num_splits
    inverse_permutation_indices_list = []
    data_list = []
    for data_idx in xrange(num_splits):
        sub_num_clusters = 2**(1+data_idx)
        data_i = gen_data(
            gen_seed=numpy.random.randint(sys.maxint),
            num_clusters=sub_num_clusters,
            num_cols=cols_per_split,
            num_rows=num_rows,
            beta_d=beta_d
            )
        data_list.append(data_i)

    permutation_indices = numpy.random.permutation(xrange(num_rows))
    inverse_permutation_indices = numpy.argsort(permutation_indices)
    inverse_permutation_indices_list.append(inverse_permutation_indices)

    data = numpy.hstack(data_list)[permutation_indices]

    # this is just to visualize, data is already generated
    state_idx = 0
    if image_save_str is not None or plot:
        state = ds.DPMB_State(
            gen_seed=numpy.random.randint(sys.maxint),
            num_cols=num_cols,
            num_rows=num_rows,
            init_z=('balanced',2),
            init_x=data[inverse_permutation_indices_list[state_idx]]
            )
        save_str = None
        if image_save_str is not None:
            save_str = image_save_str + '_' + str(state_idx)
        state.plot(save_str=save_str)

        hf.plot_data(data=data[inverse_permutation_indices_list[state_idx]])
        pylab.savefig('just_state_'+str(state_idx))
        pylab.close()
            
    return data,inverse_permutation_indices_list

def gen_factorial_data(gen_seed,num_clusters,num_cols,num_rows,num_splits,beta_d,
                       plot=False,image_save_str=None):
    numpy.random.seed(gen_seed)
    data_list = []
    inverse_permutation_indices_list = []
    for data_idx in xrange(num_splits):
        data_i = gen_data(
            gen_seed=numpy.random.randint(sys.maxint),
            num_clusters=num_clusters,
            num_cols=num_cols/num_splits,
            num_rows=num_rows,
            beta_d=beta_d
            )
        permutation_indices = numpy.random.permutation(xrange(num_rows))
        inverse_permutation_indices = numpy.argsort(permutation_indices)
        inverse_permutation_indices_list.append(inverse_permutation_indices)
        data_list.append(numpy.array(data_i)[permutation_indices])
    data = numpy.hstack(data_list)

    # this is just to visualize, data is already generated
    if image_save_str is not None or plot:
        for state_idx in xrange(num_splits):
            state = ds.DPMB_State(
                gen_seed=numpy.random.randint(sys.maxint),
                num_cols=num_cols,
                num_rows=num_rows,
                init_z=('balanced',num_clusters),
                init_x=data[inverse_permutation_indices_list[state_idx]]
                )
            save_str = None
            if image_save_str is not None:
                save_str = image_save_str + '_' + str(state_idx)
            state.plot(save_str=save_str)

            hf.plot_data(data=data[inverse_permutation_indices_list[state_idx]])
            pylab.savefig('just_state_'+str(state_idx))
            pylab.close()
            
        
    return data,inverse_permutation_indices_list

def make_balanced_data(gen_seed,num_clusters,num_cols,num_rows,beta_d,
                       num_splits=None,
                       plot=False,image_save_str=None):

    num_splits = 2 # only two splits for now
    numpy.random.seed(gen_seed)
    rows_per_cluster = num_rows/num_clusters
    if False:
        base = (numpy.arange(rows_per_cluster)*num_clusters).tolist() * \
            num_clusters
        offset = numpy.repeat(range(num_clusters),rows_per_cluster)
        distribute_indices = numpy.array() + offset
    else:
        base = (numpy.arange(num_rows) + rows_per_cluster/4)
        distribute_indices = base % num_rows
    inverse_distribute_indices = [
        range(num_rows),
        numpy.argsort(distribute_indices)
        ]

    permutation_indices = numpy.random.permutation(range(num_rows))
    inverse_distribute_indices = [
        numpy.argsort(permutation_indices)[indices]
        for indices in inverse_distribute_indices
        ]

    data_1 = numpy.array(
        gen_data(numpy.random.randint(sys.maxint),
                 num_clusters,num_cols/2,num_rows,beta_d))
    data_2 = numpy.array(
        gen_data(numpy.random.randint(sys.maxint),
                 num_clusters,num_cols/2,num_rows,beta_d))[distribute_indices]
    data = numpy.hstack([data_1,data_2])[permutation_indices]

    # this is just to visualize, data is already generated
    if image_save_str is not None or plot:
        for state_idx in xrange(num_splits):
            state = ds.DPMB_State(
                gen_seed=numpy.random.randint(sys.maxint),
                num_cols=num_cols,
                num_rows=num_rows,
                init_z=('balanced',num_clusters),
                init_x=data[inverse_distribute_indices[state_idx]]
                )
            save_str = None
            if image_save_str is not None:
                save_str = image_save_str + '_' + str(state_idx)
            state.plot(save_str=save_str)

            hf.plot_data(data=data[inverse_distribute_indices[state_idx]])
            pylab.savefig('just_state_'+str(state_idx))
            pylab.close()

    return data,inverse_distribute_indices

def make_clean_data(gen_seed, num_clusters, num_cols, num_rows, beta_d,
                    plot=False,image_save_str=None, dir=''):
    random_state = numpy.random.RandomState(gen_seed)
    rows_per_cluster = num_rows/num_clusters
    permutation_indices = random_state.permutation(range(num_rows))
    inverse_permutation_indices = numpy.argsort(permutation_indices)
    data = numpy.array(
        gen_data(random_state.randint(sys.maxint),
                 num_clusters,num_cols,num_rows,beta_d))
    data = data[permutation_indices]
    #
    # this is just to visualize, data is already generated
    if image_save_str is not None or plot:
        state = ds.DPMB_State(
            gen_seed=random_state.randint(sys.maxint),
            num_cols=num_cols,
            num_rows=num_rows,
            init_z=('balanced',num_clusters),
            init_x=data[inverse_permutation_indices]
            )
        save_str = None
        if image_save_str is not None:
            save_str = os.path.join(dir, image_save_str)
        state.plot(save_str=save_str, show=False)
        #
        save_str = os.path.join(dir, 'just_state_' + image_save_str)
        hf.plot_data(data=data[inverse_permutation_indices])
        pylab.savefig(save_str)
        pylab.close()
    return data,inverse_permutation_indices

def pkl_mrjob_problem(gen_seed, num_rows, num_cols, num_clusters, beta_d,
                      pkl_filename=None, image_save_str=None, dir=''):
    if pkl_filename is None:
        pkl_filename = '_'.join([
                'clean_balanced_data',
                'rows', str(num_rows), 
                'cols', str(num_cols),
                'pkl.gz'
                ])
    # create the data
    data, inverse_permuatation_indices_list = make_clean_data(
        gen_seed=gen_seed,
        num_rows=num_rows,
        num_cols=num_cols,
        num_clusters=num_clusters,
        beta_d=beta_d,
        image_save_str=image_save_str,
        dir=dir,
        )
    #
    all_indices = xrange(num_rows)
    random_state = numpy.random.RandomState(gen_seed)
    test_fraction = .1
    breakpoint = int(num_rows * test_fraction)
    random_indices = random_state.permutation(all_indices)
    test_indices = random_indices[:breakpoint]
    train_indices = random_indices[breakpoint:]
    test_xs = data[test_indices]
    xs = data[train_indices]
    # set up pickle variable and actually pickle
    pkl_vals = {
        'xs':xs,
        'test_xs':test_xs,
        'num_clusters':num_clusters,
        'beta_d':beta_d,
        'gen_seed':gen_seed,
        'inverse_permuatation_indices_list':inverse_permuatation_indices_list,
        }
    rf.pickle(pkl_vals, pkl_filename, dir=dir)
    #
    return pkl_vals, pkl_filename
 
def main():
    parser = argparse.ArgumentParser('Create a synthetic problem')
    parser.add_argument('gen_seed',type=int)
    parser.add_argument('num_cols',type=int)
    parser.add_argument('num_rows',type=int)
    parser.add_argument('num_clusters',type=int)
    parser.add_argument('num_splits',type=int)
    parser.add_argument('--beta_d',default=1.0,type=float)
    parser.add_argument('--pkl_file',default='structured_problem.pkl.gz',type=str)
    parser.add_argument('--image_save_str',default=None,type=str)
    parser.add_argument('--problem_type',default='factorial',type=str)
    args,unkown_args = parser.parse_known_args()

    generator = None
    if args.problem_type == 'factorial':
        generator = gen_factorial_data
    elif args.problem_type == 'balanced':
        generator = make_balanced_data
    elif args.problem_type == 'hierarchical':
        generator = gen_hierarchical_data
    else:
        raise Exception('unknown problem type: ' + args.problem_type)

    data,inverse_permutation_indices_list = generator(
        gen_seed=args.gen_seed,
        num_cols=args.num_cols,
        num_rows=args.num_rows,
        num_clusters=args.num_clusters,
        num_splits=args.num_splits,
        beta_d=args.beta_d,
        image_save_str=args.image_save_str)

    pkl_vals = {
        'data':data,
        'inverse_permutation_indices_list':inverse_permutation_indices_list,
        'num_clusters':args.num_clusters,
        'zs_to_permute':numpy.repeat(xrange(args.num_clusters),
                                     args.num_rows/args.num_clusters),
        'beta_d':args.beta_d,
        'gen_seed':args.gen_seed,
        'num_splits':args.num_splits
        }

    rf.pickle(pkl_vals, args.pkl_file, dir=S.data_dir)

if __name__ == '__main__':
    main()
