Hysteresis threshold for Zenoss
===============================

This Zenpack provides a new threshold type: a hysteresis threshold. 
Implementation is based on a stock MinMaxThreshold and adds three parameters: M, N and K.

- M - is "a history size"
- N - is "how many measurements out of M should fail to mark threshold as broken"
- K - is "how many sequential measurements should fit a threshold to generate clearing event"

So if you have M = 12, N=7 and K=6 then this threshold stores history of 12 measurements. If 7 of them are faulty - you'll recieve an event. And this event will only be cleared after 6 sequential good measurements.

General recommendation is to keep N and K less than M (or the whole thing won't work), have N+K>M, so that you won't have flapping service.

####Some key features of the implementation:
* if a measurements violates minimum or maximum value of a threshold, threshold is called "violated"
* while a threshold is violated, but less than N times out of last M measurements, we generate a "notice" level event
* while a threshold is violated less than N times out of last M measurements, we send clear events as they appear
* if a threshold is violated at least N times out of last M measurements, we generate events of a given severity and process escalation as usual MinMaxThreshold. The threshold is marked as broken
* if a threshold was broken we are waiting till K "good" measurements in a row to send a clearing event
* service restart doesn't affect nor events history, nor thresholds breaks state 

####Implementation details
Implementation stores a list of M elements (0 for a good measurement and 1 for a bad measurement) in a deque class object which is loaded from a pickle every check time.

Pickles are stored locally where an RRDDaemon is launched (e.g. zenperfsnmp). So if you have several daemons monitoring 1 device you might want to move loadHystState() call into __init__() method which will make history storage centralized.

