import keras
from keras import layers
from keras import models
from keras.models import Model
import numpy as np
from keras import backend as K
from keras.activations import relu
from keras.layers import Input,Conv2D,LeakyReLU,BatchNormalization,MaxPool2D,Dense
from keras.layers import UpSampling2D,Add,Cropping2D

W,H,C = (256,256,3)

class SharpGan():

    """
    Loss function for generator
    """
    def loss_G(self,y_true, y_pred):
        # L1 Error, I am not using MSE
        L1_distance = K.mean(K.abs(y_true-y_pred))

        # SSIM error, or D-SSIM = (1-SSIM)
        # x = K.mean(y_pred,axis=0)
        # y = K.mean(y_true,axis=0)
        x = y_true
        y = y_pred
        ave_x = K.mean(x)
        ave_y = K.mean(y)
        var_x = K.var(x)
        var_y = K.var(y)
        covariance = K.mean(x*y) - ave_x*ave_y
        c1 = 0.03**2
        c2 = 0.09**2
        ssim = (2*ave_y*ave_x+c1)*(2*covariance+c2)
        ssim = ssim/((K.pow(ave_x,2)+K.pow(ave_y,2)+c1) * (var_x+var_y+c2))
        dssim = 1 - ssim
        return self.l1_loss* L1_distance + self.dssim_loss*dssim

    def discriminator(self):
        input = Input(shape=(226,226,C))
        # Layer 1 to 4 are all conv with downsampling
        x = input
        for i in range(1,5):
            x = Conv2D(32,kernel_size=(3,3),strides=(1,1),padding='same',use_bias=False,
                       name = 'conv_'+str(i))(x)
            x = LeakyReLU(alpha=0.1)(x)
            x = BatchNormalization()(x)
            x = MaxPool2D(pool_size=(2,2))(x)

        for i in range(5,8):
            x = Conv2D(64,kernel_size=(2,2),strides=(1,1),use_bias=False,
                       padding='valid',name ='conv_'+str(i))(x)
            x = LeakyReLU(alpha=0.1)(x)
            x = BatchNormalization()(x)
            if (i!=7):
                x = MaxPool2D(pool_size=(2,2))(x)
            x = Dense(64,activation='sigmoid')(x)

        output = Dense(1,activation='sigmoid',name='out_generator')(x)

        return Model(input,output,name='discriminator')


    def generator(self):
        input = Input((W,H,C))

        x = Conv2D(32,kernel_size=(3,3),padding='same',strides=(1,1),name=
                   'initial_conv',use_bias=False)(input)
        x = LeakyReLU(alpha=0.1)(x)
        x = BatchNormalization()(x)
        skip_connection = []

        for i in range(1,5):
            skip_connection.append(x)
            x = Conv2D(int(32*(2**i)),kernel_size=(3,3),padding='same',strides=(1,1),
                       name='conv_'+str(i),use_bias=False)(x)
            x = LeakyReLU(alpha=0.1)(x)
            x = BatchNormalization()(x)
            x = MaxPool2D(pool_size=(2,2))(x)


        x = Conv2D(512,kernel_size=(1,1),strides=(1,1),use_bias=False,name = 'conv_5')(x)
        x = LeakyReLU(alpha=0.1)(x)
        x = BatchNormalization()(x)


        x = Conv2D(512,kernel_size=(1,1),strides=(1,1),use_bias=False,name = 'conv_6')(x)
        x = LeakyReLU(alpha=0.1)(x)
        x = BatchNormalization()(x)

        shape = 16
        a_shape = 16
        t_shape = 1
        for i in range(7,11):
            x = UpSampling2D(size=(2,2),name = 'upsample_'+str(i))(x)
            filters = int(512/(2**(i-6)))
            if i == 10:
                filters = 32
            x = Conv2D(filters= filters,kernel_size=(3,3),strides=(1,1),padding='valid',
                       use_bias=False,name = 'up_conv_'+str(i),activation='relu')(x)
            x = BatchNormalization()(x)
            shape = shape*2
            shape = shape-2
            a_shape = a_shape * 2
            t_shape = a_shape-shape
            # print(shape,a_shape)
            if t_shape%2 == 0:
                t_shape = (int(t_shape/2),int(t_shape/2))
            elif t_shape%2 == 1:
                t_shape = ((int(t_shape/2),int(t_shape/2)+1),(int(t_shape/2),int(t_shape/2)+1))
            cropped = Cropping2D(int((a_shape-shape)/2))(skip_connection[6-i])
            x = Add(name = 'concat_data'+str(i))([x,cropped])


        x = Conv2D(3,kernel_size=(1,1))(x)
        x = Dense(3,activation='sigmoid',name='out_generator')(x)



        return Model(input,x,name='generator')


    def create_GAN(self):
        self.D.trainable = False
        output = self.D(self.G.output)
        self.GAN = Model(self.G.input,[self.G.output, output])
        self.GAN._make_predict_function()
        GAN_optimizer = keras.optimizers.Adam(lr=1e-3)
        self.GAN.compile(optimizer=GAN_optimizer, loss={
            'out_generator': self.loss_G,
            'discriminator': 'mean_squared_error'})
        return self.GAN


    def __init__(self):
        self.l1_loss = 0.1
        self.dssim_loss = 0.5

        self.D = self.discriminator()
        self.D._make_predict_function()
        D_optimizer = keras.optimizers.Adam(lr = 1e-5) #Hopefully helps when discriminator too strong
        self.D.compile(optimizer=D_optimizer, loss='mean_squared_error')

        self.G = self.generator()
        self.G._make_predict_function()
        G_optimizer = keras.optimizers.Adam(lr = 1e-3)
        self.G.compile(optimizer=G_optimizer,loss = self.loss_G)

        self.GAN = self.create_GAN()
