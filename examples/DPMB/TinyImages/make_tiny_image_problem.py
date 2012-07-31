#!python
import os
import datetime
import argparse
#
import numpy
#
import Cloudless.examples.DPMB.TinyImages.loadTinyImages as lti
reload(lti)
import Cloudless.examples.DPMB.remote_functions as rf
reload(rf)
import Cloudless.examples.DPMB.s3_helper as s3_helper
reload(s3_helper)
import Cloudless.examples.DPMB.settings as settings
reload(settings)
import Cloudless.examples.DPMB.FeatureExtraction.binarized_pca_representation \
    as bpr
reload(bpr)


# parse some arguments
parser = argparse.ArgumentParser('Script to read in N image pieces and create a problem file')
parser.add_argument('--num_pieces',default=20,type=int)
args, unknown_args = parser.parse_known_args()
num_pieces = args.num_pieces

# set some parameters
n_test = int(.01*num_pieces*10000)
base_dir = '/mnt/' if settings.is_aws else '/media/VonNeumann/'
bucket_dir = 'TinyImages'
local_dir = os.path.join(base_dir, bucket_dir)
problem_file = 'tiny_image_problem_' + str(num_pieces) + '.pkl.gz'
full_problem_file = os.path.join(local_dir, problem_file)
#
data_piece_filter = lambda x : x.find('_data')!=-1

# make sure files are in place
if not os.path.isdir(local_dir): os.makedirs(local_dir)
s3 = s3_helper.S3_helper(
    bucket_str=settings.bucket_str, bucket_dir=bucket_dir, local_dir=local_dir)
all_files = [key.name for key in s3.bucket.list(prefix=s3.bucket_dir)]
data_files = filter(data_piece_filter, all_files)
data_files = [os.path.split(data_file)[-1] for data_file in data_files]
#
for data_file in data_files[:num_pieces]:
    s3.verify_file(data_file)
print datetime.datetime.now()
print 'Done copying down files'

# read in the data
image_list = []
image_indices = []
for data_file in data_files[:num_pieces]:
    full_filename = os.path.join(local_dir, data_file)
    unpickled = rf.unpickle(full_filename)
    image_list.extend(unpickled['image_list'])
    image_indices.extend(unpickled['image_indices'])
    print datetime.datetime.now()
    print 'Done reading ' + data_file

print datetime.datetime.now()
print 'Done reading files'

# run pca
image_data = numpy.array(image_list)
pca_components, medians, pca = bpr.generate_binarized_pca_model(image_data)
binarized_data = bpr.generate_binarized_pca_data(
    image_data, pca_components, medians)
print datetime.datetime.now()
print 'Done binarizing data'

# FIXME : is it appropriate for test data to be part of features extraction?
tiny_images = {
    'xs':binarized_data[:-n_test],
    'test_xs':binarized_data[-n_test:],
    'name':'tiny-images-test-bpr',
    'train_indices':image_indices[:-n_test],
    'test_indices':image_indices[-n_test:],
    }
rf.pickle(tiny_images, full_problem_file)
print datetime.datetime.now()
print 'Done pickling problem'
s3.put_s3(problem_file)
print datetime.datetime.now()
print 'Done pushing problem up to s3'
