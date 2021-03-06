#encoding:utf-8
#数据读取脚本
import torch.utils.data as data

from PIL import Image
import os
import os.path
import numpy as np
from numpy.random import randint
from config import parser

import torch
torch.set_printoptions(precision=6)


class VideoRecord(object):
    def __init__(self, row):
        self._data = row

    @property
    def path(self):
        return self._data[0]

    @property
    def person(self):
        path_list=self._data[0]
        path_list=path_list.split('_')
        seq=path_list[-2]
        seq_id=seq[3:]
        person_id=path_list[-1]
        return  seq_id+person_id

    @property
    def start_frames(self):
        return int(self._data[1])

    @property
    def end_frames(self):
        return int(self._data[2])

    @property
    def move_label(self):
        return int(self._data[3])

    @property
    def pose_label(self):
        return int(self._data[4])

    @property
    def group_label(self):
        return int(self._data[5])
    #@property装饰器起到把方法变成属性调用的作用，可以自动实现set和get功能，实现属性操作的可控
    #VideoRecord里有三个方法，由于@property可以看成三个属性，path:图像序列文件夹路径;num_frames：帧数;label:标签
    #这是为了从list_file中提取三个属性而定义的类
"""
自定义数据读取相关类的时候需要继承torch.utils.data.Dataset这个基类。  
在myDataset类的初始化函数__init__中最重要的是self._parse_list()，也就是调用了该类的_parse_list()方法。
在该方法中，self.list_file就是训练或测试的列表文件（.txt文件），里面包含三列内容，用空格键分隔，第一列是video名，第二列是video的帧数，第三列是video的标签。
VideoRecord这个类只是提供了一些简单的封装，用来返回关于数据的一些信息（比如帧路径、该视频包含多少帧、帧标签）。
因此最后self.video_list的内容就是一个长度为训练数据数量的列表，列表中的每个值都是VideoRecord对象，
该对象包含一个列表和3个属性，列表长度为3，分别是帧路径、该视频包含多少帧、帧标签，同样这三者也是三个属性的值。

"""
class myDataset(data.Dataset):
    def __init__(self, root_path, list_file,
                 num_segments=3, new_length=1, transform=None,
                 random_shift=True, test_mode=False):

        self.root_path = root_path
        self.list_file = list_file
        self.num_segments = num_segments
        self.new_length = new_length
        self.transform = transform
        self.random_shift = random_shift
        self.test_mode = test_mode


        self._parse_list()#运行分析列表函数，也就是把list_file中的路径+帧数+标签的格式存储进视频列表videolist


    def _parse_list(self):
        self.video_list = [VideoRecord(x.strip().split(' ')) for x in open(self.list_file)]
        #strip()清除开头和结尾的字符，此处为空格
        #split()按指定分隔符将字符串分串(此处为字符串中间的空格，比如‘Swing_g08_c04 159 88’变为‘Swing_g08_c04‘,’159‘,’88’)
    """
    在myDataset类的_sample_indices方法中，average_duration表示某个视频分成self.num_segments份的时候每一份包含多少帧图像，
    因此只要该视频的总帧数大于等于self.num_segments，就会执行if average_duration > 0这个条件，在该条件语句下offsets的计算分成两部分，
    np.multiply(list(range(self.num_segments)), average_duration)相当于确定了self.num_segments个片段的区间，
    randint(average_duration, size=self.num_segments)则是生成了self.num_segments个范围在0到average_duration的数值，
    二者相加就相当于在这self.num_segments个片段中分别随机选择了一帧图像。
    因此在__getitem__方法中返回的segment_indices就是一个长度为self.num_segments的列表，表示帧的index。

    """
    def _sample_indices(self, record):
        """

        :param record: VideoRecord
        :return: list
        """

        #实际输入的帧数是停止帧数与起始帧数的差减1,这是为了避免取到边界
        average_duration = (record.end_frames-record.start_frames -2 - self.new_length + 1) // self.num_segments #视频分成num_segments份后每份的帧数
        #比如num_segments=3,num_frames=150,则average_duration=50,区间为[0,49],[50,99],[100,149]
        if average_duration > 0:
            offsets = np.multiply(list(range(self.num_segments)), average_duration) + randint(average_duration, size=self.num_segments)
        #offsets=[0,1,2]*50+3*rand(0,50),假设rand(0,50)=[2,25,48]
        #则offsets=[2,50+25,100+48]
        elif record.end_frames-record.start_frames -1 > self.num_segments:
            offsets = np.sort(randint(record.end_frames-record.start_frames -1 - self.new_length + 1, size=self.num_segments))
        else:
            offsets = np.zeros((self.num_segments,))

        #if len(os.listdir(record.path))//3 > record.end_frames-2:
        #    offsets +=record.start_frames
        # 如果出现人不在第一帧出现且只有一种动作标签的情况，由于图片序号仍是从1开始的，就不能加偏移量（起始帧数）;
        # 而如果人存在两个动作以上且从第一帧开始，之后的动作必然要和图片序号对应，就需要偏移量，这里用图片数量和停止帧数对比进行判断
        # 如果图片数量大于停止帧数减2，一般认为是同一个人的第一个动作之后的动作，不从第一帧开始，加偏移量（起始帧数）.
        #print("train_offset:"+str(offsets+1))
        offsets[0]+=1
        offsets[2]-=1
        return offsets + record.start_frames #返回[3,76,149],+1是因为offsets的取值是[0,149],标签则是[1,150]


    def _get_val_indices(self, record):
        if record.end_frames-record.start_frames -1 > self.num_segments + self.new_length - 1:
            tick = (record.end_frames-record.start_frames -1 - self.new_length + 1) / float(self.num_segments)
            offsets = np.array([int(tick / 2.0 + tick * x) for x in range(self.num_segments)])
            #和上面的offset计算方式差不多，区别在于取每个区间的中间一帧，沿用上面的例子就是offsets=[25,75,125]
        else:
            offsets = np.zeros((self.num_segments,))

        #if len(os.listdir(record.path)) // 3 > record.end_frames - 2:
        #    offsets += record.start_frames

        #print("val_offset:"+str(offsets+1))
        return offsets + 1
    """
    在myDataset类的_get_test_indices方法中，就是将输入video按照相等帧数距离分成self.num_segments份，
    最终返回的offsets就是长度为self.num_segments的numpy array，表示从输入video中取哪些帧作为模型的输入。
    该方法是模型测试的时候才会调用。
    """
    def _get_test_indices(self, record):

        tick = (record.end_frames-record.start_frames -1 - self.new_length + 1) / float(self.num_segments)

        offsets = np.array([int(tick / 2.0 + tick * x) for x in range(self.num_segments)])
        #和get_val_indices方法一模一样，取区间中间一帧，也为[25,75,125]

        #if len(os.listdir(record.path)) // 3 > record.end_frames - 2:
        #    offsets += record.start_frames

        return offsets + 1
    """
    前面提到在运行for i, (input, target) in enumerate(train_loader)的时候最终会调用myDataset类的__getitem__方法，该方法就是用来返回具体数据的。
    前面介绍过myDataset类的初始化函数__init__，在那里面都是一些初始化或定义操作，真正的数据读取操作是在__getitem__方法中。
    在__getitem__方法中，record = self.video_list[index]得到的record就是一帧图像的信息，index是随机的，这个和前面数据读取中的shuffle参数对应。
    在训练的时候，self.test_mode是False，所以执行if语句，另外self.random_shift默认是True，所以最后执行的是segment_indices = self._sample_indices(record)。
    在测试的时候，会设置self.test_mode为True，这样的话就会执行segment_indices = self._get_test_indices(record)。最后再通过get方法返回。接下来分别介绍这三个方法。
    """
    def __getitem__(self, index):
        record = self.video_list[index]#index为何是随机的？这要结合DataLoader里的shuffle参数，Dataset类里并没有对index进行设置

        if not self.test_mode:
            segment_indices = self._sample_indices(record) if self.random_shift else self._get_val_indices(record)
        else:
            segment_indices = self._get_test_indices(record)

        #print("path: "+record.path+" start_frame: "+str(record.start_frames)+" end_frame: "+str(record.end_frames))
        #print("move_label: "+str(record.move_label)+" pose_label: "+str(record.pose_label)+" group_label: "+str(record.group_label))
        return self.get(record, segment_indices) #返回一个Tensor数据和一个int标签，格式见注释
    """
    在myDataset类的get方法中，先通过seg_imgs = self._load_image(record.path, p)来读取图像数据。
    _load_image方法中主要就是采用PIL库的Image模块来读取图像数据，该方法比较固定，一般作为当前类的一个方法比较合适，另外区分RGB和Flow数据读取的原因主要是图像名称不同。
    对于RGB或RGBDiff数据，返回的seg_imgs是一个长度为1的列表，对于Flow数据，返回的seg_imgs是一个长度为2的列表，然后将读取到的图像数据合并到images这个列表中。
    另外对于RGB而言，self.new_length是1，这样images的长度就是indices的长度；
    对于Flow而言，self.new_length是5，这样images的长度就是indices的长度乘以(5*2)。
    process_data = self.transform(images)将list类型的images封装成了Tensor，
    在训练的时候：对于RGB输入，这个Tensor的尺寸是(3*self.num_segments,224,224)，其中3表示3通道彩色；
    对于Flow输入，这个Tensor的尺寸是(self.num_segments*2*self.new_length,224,224)，其中第一维默认是30(3*2*5)。因此，最后get方法返回的是一个Tensor的数据和一个int的标签。

    """
    def get(self, record, indices):

        coordinate=list()

        features_sum =list()#定义一个列表

        for seg_ind in indices:
            #print("indices=%s,seg_ind=%s,startframes=%d,endframes=%d,path=%s,%r"%
            #      (indices,seg_ind,record.start_frames,record.end_frames,record._data[0],
            #       os.path.exists(str(record._data[0])+'/RGB/img_%05d.jpg.txt'%(seg_ind))))
            if os.path.exists(str(record._data[0])+'/RGB/img_%05d.jpg.txt'%(seg_ind)):
                p = int(seg_ind)
            else:
                p = int(seg_ind) - record.start_frames
            #print("p=%d"%(p))


            #get label and coordinates
            idx=str(record._data[0]).split('/')
            idx=idx[-1].split('_')
            idx=[idx[-2][-2:],idx[-1]]

            with open('./labels_ready/seq%s/track%d_%s_%s.txt'%(idx[0],int(idx[0]),idx[1],record.move_label),'r') as f_xy:
                for line in f_xy:
                    line=line.split(' ')
                    if int(line[1])==p+ int(record.start_frames):
                        _x=int(line[2])
                        _y=int(line[3])
                        _width=int(line[4])
                        _height=int(line[5])

                        coordinate.append([_x+_width/2,_y+_height/2])
            f_xy.close()


            #get features
            features=list()
            #print(str(record._data[0])+'/RGB/img_%05d.jpg.txt'%(p))
            with open(str(record._data[0])+'/RGB/img_%05d.jpg.txt'%(p),'r') as f_rgb:
                for line in f_rgb:
                    features.append(float(line.strip('\n')))
            f_rgb.close()

            #flow_window
            p_flow=p

            for i in range(p_flow,p_flow+6):
                if not os.path.exists(str(record._data[0])+'/Flow/flow_x_%05d.jpg.txt'%(i)):
                    p_flow-=1

            for i in range(p_flow,p_flow+6):
                #print(str(record._data[0]) + '/Flow/flow_x_%05d.jpg.txt'%(i))
                with open(str(record._data[0])+'/Flow/flow_x_%05d.jpg.txt'%(i),'r') as f_flow:
                    for line in f_flow:
                        features.append((float(line.strip('\n'))))
                f_flow.close()
            for i in range(p_flow,p_flow+6):
                #print(str(record._data[0]) + '/Flow/flow_y_%05d.jpg.txt' % (i))
                with open(str(record._data[0])+'/Flow/flow_y_%05d.jpg.txt'%(i),'r') as f_flow:
                    for line in f_flow:
                        features.append((float(line.strip('\n'))))
                f_flow.close()

            features_sum.append(features)
        features_sum=np.array(features_sum)

        #multiply features with pose in binary code
        pose_bin=int(bin(record.pose_label-1)[2:])
        pose_bin='{:0>3d}'.format(pose_bin)
        pose_bin=[int(pose_bin[0].replace('0','-1')),int(pose_bin[1].replace('0','-1')),int(pose_bin[2].replace('0','-1'))]
        pose_bin=np.array(pose_bin)



        features_mixed=np.zeros([3,79872])

        for i in range(0,len(features_sum)):

            tmp=np.append(features_sum[i]*pose_bin[0],features_sum[i]*pose_bin[1])
            tmp=np.append(tmp,features_sum[i]*pose_bin[2])

            features_mixed[i]=tmp
            del tmp
        process_data =torch.from_numpy(features_mixed).float()

        #labels mix up
        mixed_labels=[int(record.person),coordinate,int(record.move_label - 1),int(record.pose_label - 1),int(record.group_label - 1)]

        #print(record.person+" done!")
        return process_data,mixed_labels

    def __len__(self):
        return len(self.video_list)

if __name__ =="__main__":
    args = parser.parse_args()
    mydataset=myDataset("", args.train_list, num_segments=args.num_segments)
    for i in range(0,2018):
        mydataset.__getitem__(i)

    print("done!")