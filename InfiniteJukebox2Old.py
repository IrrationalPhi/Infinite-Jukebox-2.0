#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 25 14:41:25 2021
inspired by https://nolannicholson.com/2019/10/27/looping-music-seamlessly.html

@author: seanty
"""

from mpg123 import Mpg123, Out123
import numpy as np
from pydub import AudioSegment
import sys

class loopMusic:
    def __init__(self, filename):
        # import from Mpg123, becomes PCM file
        pcm = Mpg123(filename)
        # filename for later when extending
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
        
        # checked and first and last frames have diff len
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
            fft_2d_sub.T, 0)
        
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
        for start in range(450, len(self.max_freq) - length, int(len(self.max_freq) / 10)):
            for end in range(start+length, len(self.max_freq) - length):
                corr = self._auto_corr(start, end, length)
                if corr > max_corr:
                    max_corr = corr
                    start_best = start
                    end_best = end
        
        print("... Done!")
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
    
    
def main():
    argv = sys.argv
    file = argv[1]
    response = int(input("0: infinite jukebox, 1: extender\n"))
    if response == 0:
        loop(file)
    else:
        length = int(input("enter seconds to extend to:\n"))
        song = loopMusic(file)
        song.extend(length)
        

if __name__ == "__main__":
    main()    