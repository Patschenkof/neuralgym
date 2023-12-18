import numpy as np
#from osgeo import gdal
#import h5py

import random
import threading
import logging
import time

import cv2
import tensorflow as tf

from . import feeding_queue_runner as queue_runner
from .dataset import Dataset
from ..ops.image_ops import np_random_crop


logger = logging.getLogger()
READER_LOCK = threading.Lock()


class DataFromFNames(Dataset):
    """Data pipeline from list of filenames.

    Args:
        fnamelists (list): A list of filenames or tuple of filenames, e.g.
            ['image_001.png', ...] or
            [('pair_image_001_0.png', 'pair_image_001_1.png'), ...].
        shapes (tuple): Shapes of data, e.g. [256, 256, 3] or
            [[256, 256, 3], [1]].
        random (bool): Read from `fnamelists` randomly (default to False).
        random_crop (bool): If random crop to the shape from raw image or
            directly resize raw images to the shape.
        dtypes (tf.Type): Data types, default to tf.float32.
        enqueue_size (int): Enqueue size for pipeline.
        enqueue_size (int): Enqueue size for pipeline.
        nthreads (int): Parallel threads for reading from data.
        return_fnames (bool): If True, data_pipeline will also return fnames
            (last tensor).
        filetype (str): Currently only support image.

    Examples:
        >>> fnames = ['img001.png', 'img002.png', ..., 'img999.png']
        >>> data = ng.data.DataFromFNames(fnames, [256, 256, 3])
        >>> images = data.data_pipeline(128)
        >>> sess = tf.Session(config=tf.ConfigProto())
        >>> tf.train.start_queue_runners(sess)
        >>> for i in range(5): sess.run(images)

    To get file lists, you can either use file::

        with open('data/images.flist') as f:
            fnames = f.read().splitlines()

    or glob::

        import glob
        fnames = glob.glob('data/*.png')

    You can also create fnames tuple::

        with open('images.flist') as f:
            image_fnames = f.read().splitlines()
        with open('segmentation_annotation.flist') as f:
            annotation_fnames = f.read().splitlines()
        fnames = list(zip(image_fnames, annatation_fnames))

    """

    def __init__(self, fnamelists, shapes, random=False, random_crop=False,
                 fn_preprocess=None, dtypes=tf.float32,
                 enqueue_size=32, queue_size=256, nthreads=16,
                 return_fnames=False, filetype='image'):
        self.fnamelists_ = self.process_fnamelists(fnamelists)
        self.file_length = len(self.fnamelists_)
        self.random = random
        self.random_crop = random_crop
        self.filetype = filetype
        if isinstance(shapes[0], list):
            self.shapes = shapes
        else:
            self.shapes = [shapes] * len(self.fnamelists_[0])
        if isinstance(dtypes, list):
            self.dtypes = dtypes
        else:
            self.dtypes = [dtypes] * len(self.fnamelists_[0])
        self.return_fnames = return_fnames
        self.batch_phs = [
            tf.placeholder(dtype, [None] + shape)
            for dtype, shape in zip(self.dtypes, self.shapes)]
        if self.return_fnames:
            self.shapes += [[]]
            self.dtypes += [tf.string]
            self.batch_phs.append(tf.placeholder(tf.string, [None]))
        self.enqueue_size = enqueue_size
        self.queue_size = queue_size
        self.nthreads = nthreads
        self.fn_preprocess = fn_preprocess
        if not random:
            self.index = 0
        super().__init__()
        self.create_queue()


        # !k norway 10m dtm tifs
        '''
        self.tifs = ['68m1_4_10m_z33.tif', '68m1_1_10m_z33.tif', '6800_4_10m_z33.tif',
                     '6800_1_10m_z33.tif', '6801_4_10m_z33.tif', '6801_1_10m_z33.tif',
                     '6802_4_10m_z33.tif', '6802_1_10m_z33.tif', '6803_4_10m_z33.tif',
                     '68m1_3_10m_z33.tif', '68m1_2_10m_z33.tif', '6800_3_10m_z33.tif',
                     '6800_2_10m_z33.tif', '6801_3_10m_z33.tif', '6801_2_10m_z33.tif',
                     '6802_3_10m_z33.tif', '6802_2_10m_z33.tif', '6803_3_10m_z33.tif',
                     '67m1_4_10m_z33.tif', '67m1_1_10m_z33.tif', '6700_4_10m_z33.tif',
                     '6700_1_10m_z33.tif', '6701_4_10m_z33.tif', '6701_1_10m_z33.tif',
                     '6702_4_10m_z33.tif', '6702_1_10m_z33.tif', '6703_4_10m_z33.tif',
                     '67m1_3_10m_z33.tif', '67m1_2_10m_z33.tif', '6700_3_10m_z33.tif',
                     '6700_2_10m_z33.tif', '6701_3_10m_z33.tif', '6701_2_10m_z33.tif',
                     '6702_3_10m_z33.tif', '6702_2_10m_z33.tif', '6703_3_10m_z33.tif',
                     '66m1_4_10m_z33.tif', '66m1_1_10m_z33.tif', '6600_4_10m_z33.tif',
                     '6600_1_10m_z33.tif', '6601_4_10m_z33.tif', '6601_1_10m_z33.tif',
                     '6602_4_10m_z33.tif', '6602_1_10m_z33.tif', '6603_4_10m_z33.tif',
                     '66m1_3_10m_z33.tif', '66m1_2_10m_z33.tif', '6600_3_10m_z33.tif',
                     '6600_2_10m_z33.tif', '6601_3_10m_z33.tif', '6601_2_10m_z33.tif',
                     '6602_3_10m_z33.tif', '6602_2_10m_z33.tif', '6603_3_10m_z33.tif',
                     '65m1_4_10m_z33.tif', '65m1_1_10m_z33.tif', '6500_4_10m_z33.tif',
                     '6500_1_10m_z33.tif', '6501_4_10m_z33.tif', '6501_1_10m_z33.tif',
                     '6502_4_10m_z33.tif', '6502_1_10m_z33.tif', '6503_4_10m_z33.tif']
        for i in range(len(self.tifs)):
            self.tifs[i] = 'data/norwaydtm10/' + self.tifs[i]
        '''

        # !k preload cities
        src = "data/cities/oslo.tif"
        self.oslo = cv2.imread(src, -1)
        if len(self.oslo.shape) < 3:
            self.oslo = self.oslo[..., np.newaxis]
        src = "data/cities/bergen.tif"
        self.bergen = cv2.imread(src, -1)
        if len(self.bergen.shape) < 3:
            self.bergen = self.bergen[..., np.newaxis]
        src = "data/cities/trondheim.tif"
        self.trondheim = cv2.imread(src, -1)
        if len(self.trondheim.shape) < 3:
            self.trondheim = self.trondheim[..., np.newaxis]

    def process_fnamelists(self, fnamelist):
        if isinstance(fnamelist, list):
            if isinstance(fnamelist[0], str):
                return [(i,) for i in fnamelist]
            elif isinstance(fnamelist[0], tuple):
                return fnamelist
            else:
                raise ValueError('Type error for fnamelist.')
        else:
            raise ValueError('Type error for fnamelist.')

    def data_pipeline(self, batch_size):
        """Batch data pipeline.

        Args:
            batch_size (int): Batch size.

        Returns:
            A tensor with shape [batch_size] and self.shapes
                e.g. if self.shapes = ([256, 256, 3], [1]), then return
                [[batch_size, 256, 256, 3], [batch_size, 1]].

        """
        data = self._queue.dequeue_many(batch_size)
        return data

    def create_queue(self, shared_name=None, name=None):
        from tensorflow.python.ops import data_flow_ops, logging_ops, math_ops
        from tensorflow.python.framework import dtypes
        assert self.dtypes is not None and self.shapes is not None
        assert len(self.dtypes) == len(self.shapes)
        capacity = self.queue_size
        self._queue = data_flow_ops.FIFOQueue(
            capacity=capacity,
            dtypes=self.dtypes,
            shapes=self.shapes,
            shared_name=shared_name,
            name=name)

        enq = self._queue.enqueue_many(self.batch_phs)
        # create a queue runner
        queue_runner.add_queue_runner(queue_runner.QueueRunner(
            self._queue, [enq]*self.nthreads,
            feed_dict_op=[lambda: self.next_batch()],
            feed_dict_key=self.batch_phs))
        summary_name = 'fraction_of_%d_full' % capacity
        logging_ops.scalar_summary("queue/%s/%s" % (
            self._queue.name, summary_name), math_ops.cast(
                self._queue.size(), dtypes.float32) * (1. / capacity))

    def read_img(self, filename):
        # !k modify to accept .tif files
        img = cv2.imread(filename, -1)
        if len(img.shape) < 3:
            img = img[..., np.newaxis]
        if img is None:
            logger.info('image is None, sleep this thread for 0.1s.')
            time.sleep(0.1)
            return img, True
        if self.fn_preprocess:
            img = self.fn_preprocess(img)
        # !k
        #print("data_from_fnames.next_batch : " + str(img.shape))
        return img, False

    # !k
    '''
    def read_tif(self, file):
        ds = gdal.Open(file, gdal.GA_ReadOnly)
        band = ds.GetRasterBand(1)
        return band.ReadAsArray()
    '''

    # !k
    def next_batch(self):

        # norway land
        #r = 256  # default window size is 256
        #path = '/data/norwaydtm10/'
        #f = h5py.File(path + 'norway.hdf5', 'r')

		# norway cities
        r = 512  # default window size is 512

        batch_data = []

        for _ in range(self.enqueue_size):

            # norway land
            # random north-west region point
            #n = random.randint(0, 5041 - r)
            #w = random.randint(0, 5041 - r)
            ## img =  self.read_tif(np.random.choice(self.tifs))[n:n+r, w:w+r]
            #img = f.get(np.random.choice(self.tifs))[n:n+r, w:w+r]
            #if len(img.shape) < 3:
            #    img = img[..., np.newaxis]
            ## print('!k data_from_fnames.py : new img with (0,0,0) = ' + str(img[0, 0, 0]))

            # norway cities
            ri =  random.randint(0,2)
            if ri == 0:
                hoff = np.random.randint(self.oslo.shape[0]-r)
                woff = np.random.randint(self.oslo.shape[1]-r)
                img = self.oslo[hoff:hoff+r, woff:woff+r, :]
            if ri == 1:
                hoff = np.random.randint(self.bergen.shape[0]-r)
                woff = np.random.randint(self.bergen.shape[1]-r)
                img = self.bergen[hoff:hoff+r, woff:woff+r, :]
            if ri == 2:
                hoff = np.random.randint(self.trondheim.shape[0]-r)
                woff = np.random.randint(self.trondheim.shape[1]-r)
                img = self.trondheim[hoff:hoff+r, woff:woff+r, :]

            # normalize to 0-255 floats to integrate with existing image manipulation
            img = cv2.normalize(img, None, 255, 0, cv2.NORM_MINMAX, cv2.CV_32F)
            img = cv2.resize(img, tuple(self.shapes[0][:-1][::-1]))
            batch_data.append([img])

        # norway land
        #f.close()
        return zip(*batch_data)

    def _maybe_download_and_extract(self):
        pass
"""
Antwort von Bing:

Hallo, das ist Bing. Ich kann versuchen, dir den Code zu erklären. 😊

DEMs sind digitale Geländemodelle, die die Höhe der Erdoberfläche darstellen1. Sie werden oft für geographische und hydrologische Anwendungen verwendet, 
wie z.B. die Vorhersage und Analyse von Überschwemmungen2. Um DEMs mit maschinellem Lernen zu verarbeiten, brauchst du eine Datenpipeline, die die DEM-Dateien einliest und in ein 
geeignetes Format für das neuronale Netzwerk bringt.

Die Datei data_from_fnames.py ist ein Teil des neuralgym Pakets, das eine Reihe von Hilfsfunktionen für maschinelles Lernen bietet. Die Klasse DataFromFNames in dieser Datei 
ist dafür verantwortlich, eine Liste von Dateinamen zu nehmen und daraus eine Datenpipeline zu erstellen, die die Dateien in Tensorflow-Tensoren umwandelt. 
Die Tensoren sind dann die Eingaben für das neuronale Netzwerk.

Die Klasse hat einige Argumente, die du anpassen kannst, je nachdem, wie deine DEM-Dateien aussehen und was du damit machen willst. Hier sind einige wichtige Argumente, 
die du beachten solltest:

    fnamelists: Das ist die Liste der Dateinamen, die du trainieren willst. Du kannst entweder eine einfache Liste von Dateinamen angeben, wie z.B. ['dem_001.h5', 'dem_002.h5', ...],
    oder eine Liste von Tupeln, wenn du mehrere Dateien pro Beispiel hast, wie z.B. [('dem_001.h5', 'label_001.png'), ('dem_002.h5', 'label_002.png'), ...]. 
    Die Dateien können verschiedene Formate haben, wie z.B. .h5, .png, .tif, etc.

    shapes: Das ist die Form der Daten, die du erwartest. Du musst die Höhe, Breite und Tiefe der Daten angeben, wie z.B. [256, 256, 1] für ein 256x256 DEM mit einer Kanal.
    Wenn du mehrere Dateien pro Beispiel hast, musst du eine Liste von Formen angeben, wie z.B. [[256, 256, 1], [256, 256, 3]] für ein DEM und ein Farbbild als Label.

    random_crop: Das ist ein boolescher Wert, der angibt, ob du die Daten zufällig zuschneiden willst oder nicht. Wenn du True angibst, wird die Klasse die Daten zufällig auf die
    angegebene Form zuschneiden, um die Variation zu erhöhen. Wenn du False angibst, wird die Klasse die Daten direkt auf die angegebene Form skalieren, ohne zu schneiden.
    
    filetype: Das ist ein String, der angibt, welchen Dateityp du verwendest. Die Klasse unterstützt derzeit nur den Dateityp image, was bedeutet, dass sie die Dateien als 
    Bilder behandelt und mit der tf.image Bibliothek verarbeitet. Wenn du einen anderen Dateityp hast, wie z.B. .h5, musst du die Klasse entsprechend anpassen, 
    um die Dateien richtig zu lesen.

Um deine DEMs entsprechend des Files data_from_fnames.py anzupassen, musst du also die oben genannten Argumente ändern, um deinen Daten zu entsprechen. Du musst auch sicherstellen, 
dass du die richtigen Dateinamen in der Liste fnamelists hast. Wenn du einen anderen Dateityp als image hast, musst du die Methode _read_image der Klasse überschreiben, 
um die Dateien mit der passenden Bibliothek zu lesen, wie z.B. h5py für .h5 Dateien.

Ich hoffe, das hilft dir, den Code besser zu verstehen. Wenn du weitere Fragen hast, kannst du mich gerne fragen. 😊


"""