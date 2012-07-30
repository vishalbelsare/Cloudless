#!python
from PIL import Image
import random
#
import numpy
#


filename = '/media/VonNeumann/tiny_images.bin'
sx = 32
num_channels = 3
nbytesPerChannel = sx*sx
nbytesPerImage = nbytesPerChannel*num_channels
total_num_images = 79302017

def reorder_image_bytes(raw_image_data):
    red_channel = raw_image_data[(0*nbytesPerChannel):(1*nbytesPerChannel)]
    green_channel = raw_image_data[(1*nbytesPerChannel):(2*nbytesPerChannel)]
    blue_channel = raw_image_data[(2*nbytesPerChannel):(3*nbytesPerChannel)]
    new_pixels = []
    for r,g,b in zip(red_channel,green_channel,blue_channel):
        new_pixels.append(''.join([r,g,b]))
    #
    image_data = ''.join(new_pixels)
    return image_data

def reorder_per_cifar(image_str_data):
    image_data = [ord(x) for x in image_str_data]
    image_data_reordered = []
    for x in range(num_channels):
        current_color = image_data[x::num_channels]
        current_color_reordered = [
            x for x in 
            numpy.array(current_color).reshape((sx,sx)).T.flatten()
            ]
        image_data_reordered.extend(current_color_reordered)
    return numpy.array(image_data_reordered)

def read_images(n_images,seed=0,image_indices=None,save_image=False,per_cifar=True):
    if image_indices is None:
        random.seed(seed)
        image_indices = random.sample(xrange(total_num_images),n_images)
    image_list = []
    with open(filename) as fh:
        for image_idx in image_indices:
            image_offset = image_idx * nbytesPerImage 
            fh.seek(image_offset)
            raw_image_str_data = fh.read(nbytesPerImage)
            raw_image_int_data = [ord(x) for x in raw_image_str_data]
            # if you don't do this, the data is different as determined by min,max
            image_str_data = reorder_image_bytes(raw_image_str_data)
            #
            if save_image:
                image = Image.fromstring('RGB',(sx,sx),image_str_data).transpose(
                    Image.ROTATE_270)
                image.save(str(image_idx)+'.png','PNG')
            #
            if per_cifar:
                image_list.append(reorder_per_cifar(image_str_data))
            else:
                image_list.append(image_str_data)
    return image_list,image_indices

def main():
    import csv
    import argparse
    import random
    #
    import Cloudless.examples.DPMB.FeatureExtraction.binarized_pca_representation as bpr
    reload(bpr)
    from loadTinyImage import read_images, reorder_per_cifar

    parser = argparse.ArgumentParser('Verify cifar and tiny_image data match')
    parser.add_argument('--n_images',default=10,type=int)
    args,unkown_args = parser.parse_known_args()
    n_images = args.n_images
    
    # the tiny image indices corresponding cifar indices 
    tiny_image_index_lookup = None
    # http://www.cs.utoronto.ca/~kriz/cifar_indexes
    with open('cifar_indexes') as fh:
        csv_reader = csv.reader(fh)
        tiny_image_index_lookup = [int(index[0])-1 for index in csv_reader]

    # random indices to test
    random.seed(0)
    cifar_indices = random.sample(xrange(50000),n_images)
    # sometimes a tiny_image_index is -1
    # this means the cifar image isn't from tiny images
    cifar_indices = filter(lambda x: tiny_image_index_lookup[x]!=-1,cifar_indices)
    tiny_image_indices = [
        tiny_image_index_lookup[cifar_index]
        for cifar_index in cifar_indices
        ]
    
    print 'Verifying cifar_indices: ' + str(cifar_indices)
    print 'Corresponding tiny_image_indices: ' + str(tiny_image_indices)

    # cifar data
    cifar_data, cifar_labels = bpr.read_cifar_100()
    
    # tiny image data
    tiny_images,temp_indices = read_images(
        n_images=None,
        image_indices=tiny_image_indices)
    for index in range(len(cifar_indices)):
        try:
            assert all(tiny_images[index]==cifar_data[cifar_indices[index]])
        except AssertionError,e:
            'Failed on cifar index: ' + str(cifar_indices[index])
            'Corresponding tiny_images index: ' + str(tiny_image_indices[index])

if __name__ == '__main__':
    main()
