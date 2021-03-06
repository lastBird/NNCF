# group neg_sharing
import numpy as np
import time
from utilities import get_cur_time, nan_detection
from data_utils import group_shuffle_train, GroupSampler
from train_base import TrainerBase

class Trainer(TrainerBase):
    def __init__(self, model_dict, conf, data_helper):
        super(Trainer, self).__init__(model_dict, conf, data_helper)
        self.model_train = model_dict['model_group_neg_shared']
        if conf.neg_dist != 'unigram':
            print '[WARNING] Only unigram neg_dist is currently supported ' \
                'for group_neg_shared training. Set neg_dist = unigram.'

        try: group_shuffling_trick = conf.group_shuffling_trick
        except: group_shuffling_trick = False
        self.group_shuffling_trick = group_shuffling_trick
        if group_shuffling_trick:
            _num_in_train = np.max(data_helper.data['train'], axis=0) + 1
            self._iidx = {'user': np.arange(_num_in_train[0]),
                          'item': np.arange(_num_in_train[1])}
        else:
            self.group_sampler = GroupSampler(data_helper.data['train'],
                                              group_by='item',
                                              chop=conf.chop_size)
            self.group_sample = self.group_sampler.sample

    def train(self, eval_scheme=None, use_async_eval=True):
        model_train = self.model_train
        conf = self.conf
        data_helper = self.data_helper
        batch_size_p = conf.batch_size_p
        train = data_helper.data['train']
        C = data_helper.data['C']
        group_shuffling_trick = self.group_shuffling_trick

        train_time = []
        for epoch in range(conf.max_epoch + 1):
            bb, b = 0, batch_size_p
            cost, it = 0, 0
            if group_shuffling_trick:
                train = group_shuffle_train(train, by='item', \
                    chop=conf.chop_size, iidx=self._iidx['item'])

            t_start = time.time()
            while epoch > 0 and bb < len(train):
                it += 1
                b = bb + batch_size_p
                if b > len(train):
                    # get rid of uneven tail so no need to dynamically adjust batch_size_p
                    break
                if group_shuffling_trick:
                    train_batch = train[bb: b]
                else:
                    train_batch = self.group_sample(batch_size_p)
                user_batch = train_batch[:, 0]
                item_batch = train_batch[:, 1]
                response_batch = train_batch[:, 2]
                cost += model_train.train_on_batch([user_batch, item_batch],
                                                   [response_batch])
                bb = b
            if epoch > 0:
                train_time.append(time.time() - t_start)
            print get_cur_time(), 'epoch %d (%d it)' % (epoch, it), \
                'cost %.5f' % (cost / it if it > 0 else -1),
            nan_detection('cost', cost)
            if eval_scheme is None:
                print ''
            else:
                async_eval = True \
                    if use_async_eval and epoch != conf.max_epoch else False
                try: ps[-1].join()
                except: pass
                ps = self.test(eval_scheme, use_async_eval=async_eval)
        print 'Training time (sec) per epoch:', np.mean(train_time)
