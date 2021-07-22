#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 25 14:41:25 2021
inspired by https://nolannicholson.com/2019/10/27/looping-music-seamlessly.html
"""

from mpg123 import Mpg123, Out123
import numpy as np
from pydub import AudioSegment
import os
import errno

from tkinter import *
from tkinter.filedialog import askopenfilename
from PIL import ImageTk, Image

class loopMusic:
    def __init__(self, filename):
        # import from Mpg123, becomes PCM file
        if os.path.exists(filename):
            if (filename[-4:].lower() == ".mp3"):
                pcm = Mpg123(filename)
            else:
                print("Only MP3 file types supported.")
                return
        else:
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), filename)
        # filename for later when extending
        # check if file exists and is valid
        self.filename = filename[:-4]
        
        # get frames
        ## they look like hexadecimal bytes
        self.frames = list(pcm.iter_frames())
        # extract other settings
        self.rate, self.channels, self.encoding = pcm.get_format()
        
        # computing frames
        self.frames_per_sec = self.rate * self.channels/(len(self.frames[1])/2)
        
        # for extensions
        self.sound = AudioSegment.from_mp3(filename)
        
        self._calc_freq()
        self.max_corr = self._find_loop_point()
        
    def _calc_freq(self):
        # filter out the noise by recording only max freq
        frames_fft = []
        
        # first and last frames have diff len
        # so we omit
        start_frame, end_frame = (1, len(self.frames) -1)
        for i in range(start_frame, end_frame):
            decoded = np.frombuffer(self.frames[i], dtype = np.int16) 
            # we look only at one of the channels
            split = decoded[::self.channels]
            frames_fft.append(np.abs(np.fft.rfft(split)))
            
        # convert the ffts into one 2d np arr
        fft_2d = np.stack(frames_fft)
        
        # return DFT sample freqs for later comparisons
        frame_freq = np.fft.rfftfreq(len(split))
        clip_start, clip_end = (1, 25)
        frame_freq_sub = frame_freq[clip_start:clip_end]
        fft_2d_sub = fft_2d[:, clip_start:clip_end]
        
        # remove noise by masking low amp frequencies
        fft_2d_denoise = np.ma.masked_where(
            (fft_2d_sub.T < fft_2d_sub.max() * 0.25),
            fft_2d_sub.T, copy = False)
        
        # get max freq per frame
        # remove frames whose max freq = baseline freq
        max_freq = frame_freq_sub[np.argmax(fft_2d_denoise, axis = 0)]
        self.max_freq = np.ma.masked_where(max_freq == frame_freq_sub[0], max_freq)
        
    # calculate autocorrelation of frames
    def _auto_corr(self, frame1, frame2, length):
        return np.corrcoef(
                self.max_freq[frame1: frame1+length],
                self.max_freq[frame2: frame2+length]
        )[1,0]
    
    # find loop point
    def _find_loop_point(self, length = 500):
        max_corr = -1
        start_best = -1
        end_best = -1
        
        print("Finding loop point...")
        print()
        
        # 450 was best start frame from testing
        # only tested on trails osts
        delay = 450
        for start in range(delay, len(self.max_freq) - length, int(len(self.max_freq) / 10)):
            for end in range(start+length, len(self.max_freq) - length):
                corr = self._auto_corr(start, end, length)
                if corr > max_corr:
                    max_corr = corr
                    start_best = start
                    end_best = end
        
        print("... Done!")
        print()
        print(f"Start: {self.time_of_frame(start_best)}s \nEnd: {self.time_of_frame(end_best)}s")
        print(f"Correlation: {max_corr}")
        print()

        print("Enjoy!")
        print()
        
        self.start_loop = start_best
        self.end_loop = end_best
        return max_corr
    
    # find instance of frame in track
    def time_of_frame(self, frame):
        return frame/self.frames_per_sec
    
    # looping
    def loop(self):
        out = Out123()
        # same settings as original
        out.start(self.rate, self.channels, self.encoding)

        # get trackname but remove directory stuff
        str_iter = len(self.filename)
        while self.filename[str_iter-1] != "/":
            str_iter -= 1
        trackname = self.filename[str_iter:len(self.filename)]
        print(f"Now playing: {trackname}")
        
        frame_iter = 0
        while True:
            out.play(self.frames[frame_iter])
            frame_iter += 1
            if frame_iter == self.end_loop:
                frame_iter = self.start_loop
                
    # extend track to specified length (measured in seconds)            
    def extend(self, length):
        # try converting frames into ms
        start_loop_ms = int(1000*self.time_of_frame(self.start_loop))
        end_loop_ms = int(1000*self.time_of_frame(self.end_loop))
        
        # find length of each component in ms
        len_first = start_loop_ms
        len_loop = end_loop_ms - start_loop_ms
        
        song_first = self.sound[:start_loop_ms]
        song_loop = self.sound[start_loop_ms: end_loop_ms]
        
        # convert cutoff to ms
        cutoff = 1000*length
        
        num_loops = int((cutoff - len_first)/len_loop)
        
        extended = song_first + song_loop * num_loops
        extended = extended.fade_out(3000)
        extended.export(self.filename + "Extended.mp3", format = "mp3")
        print(f"Exported to current folder as {self.filename}Extended.mp3")
        
                
def loop(filepath):
    song = loopMusic(filepath)
    print(f"Loop points: {song.time_of_frame(song.start_loop)} and {song.time_of_frame(song.end_loop)}")
    print(f"Correlation: {song.max_corr}")
    print()
    
    song.loop()

class LooperFrame(Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack()
        # self.paused = False
        self.track = None
        self.grid()
        self._create_widgets()

        # create image and resize
        pil_img = Image.open("renne.png")
        width, height = pil_img.size
        max_width, max_height = (200, 200)
        resize_ratio = min(max_width/width, max_height/height)
        new_size = (int(width * resize_ratio), int(height * resize_ratio))
        pil_img = pil_img.resize(new_size)
        
        img = ImageTk.PhotoImage(pil_img)
        img_label = Label(image = img)
        img_label.image = img
        
        img_label.place(x = 275, y = 50)
        
    def _create_widgets(self):
        self.select_track_button = Button(self, text = "Select Track", command = self.select_track, width = 25)
        self.loop_button = Button(self, text = "Loop Track", command = self.loop, width = 25)
        self.extend_button = Button(self, text = "Extend Track", command = self.extend, width = 25)
        
        self.select_track_button.grid(row = 2, column = 0)
        self.loop_button.grid(row = 4, column = 0)
        self.extend_button.grid(row = 6, column = 0)
    
    # select track to upload
    def select_track(self):
        filename = askopenfilename(initialdir = os.getcwd())
        self.update()
        self.track = loopMusic(filename)
        if self.track is not None:
            self.select_track_button["state"] = DISABLED
    
    # loop track
    def loop(self):
        self.track.loop()
    
    # extend track
    def extend(self):
        self.track.extend(1800)
    
    
def main():
    # create root window
    root = Tk()

    # set dimensions, title
    root.geometry("500x500")
    root.title("InfiniteJukebox2.0")

    # set looper
    looper = LooperFrame(root)
    looper.mainloop()

    while True:
        looper.update()
        

if __name__ == "__main__":
    main()    