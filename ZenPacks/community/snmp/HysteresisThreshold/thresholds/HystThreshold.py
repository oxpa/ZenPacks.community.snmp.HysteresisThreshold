##############################################################################
#
# Copyright (C) Zenoss, Inc. 2007, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from Products.ZenModel.ThresholdInstance import RRDThresholdInstance

__doc__ = """HystThreshold
Make threshold comparisons dynamic by using TALES expresssions,
rather than just number bounds checking.
"""

from Products.ZenUtils.Utils import zenPath, atomicWrite
import cPickle as pickle
from collections import deque
from AccessControl import Permissions

from Globals import InitializeClass
from Products.ZenModel.ThresholdClass import ThresholdClass
from Products.ZenModel.ThresholdInstance import ThresholdContext
from Products.ZenEvents import Event
from Products.ZenEvents.ZenEventClasses import Perf_Snmp
from Products.ZenUtils.ZenTales import talesEval, talesEvalStr
from Products.ZenEvents.Exceptions import pythonThresholdException, \
    rpnThresholdException

import logging
log = logging.getLogger('zen.HysteresisThreshold')

from Products.ZenUtils.Utils import unused, nanToNone

# Note:  this import is for backwards compatibility.
# Import Products.ZenRRD.utils.rpneval directy.
from Products.ZenRRD.utils import rpneval

NaN = float('nan')


class HystThreshold(ThresholdClass):
    """
    Threshold class that can evaluate RPNs and Python expressions
    """

    minval = ""
    maxval = ""
    badCount = ""
    queueSize = ""
    goodCount = ""
    eventClass = Perf_Snmp
    severity = 3
    escalateCount = 0

    _properties = ThresholdClass._properties + (
        {'id': 'minval',        'type': 'string', 'mode': 'w'},
        {'id': 'maxval',        'type': 'string', 'mode': 'w'},
        {'id': 'badCount',      'type': 'string', 'mode': 'w',
         'label': 'An alert will be raised if N of M measurements failed<br/>'
                  'Clear event will be generated only '
                  'after K sequential clear measurements'},
        {'id': 'queueSize',     'type': 'string', 'mode': 'w'},
        {'id': 'goodCount',     'type': 'string', 'mode': 'w'},
        {'id': 'escalateCount', 'type': 'int',    'mode': 'w'}
        )

    factory_type_information = (
        {
            'immediate_view': 'editHystThreshold',
            'actions':
            (
                {'id':     'edit',
                 'name':   'Hysteresis Threshold',
                 'action': 'editHystThreshold',
                 'permissions': (Permissions.view, ),
                 },
            )
        },
    )

    def createThresholdInstance(self, context):
        """Return the config used by the collector to process min/max
        thresholds. (id, minval, maxval, severity, escalateCount)
        """
        mmt = HystThresholdInstance(self.id,
                                    ThresholdContext(context),
                                    self.dsnames,
                                    minval=self.getMinval(context),
                                    maxval=self.getMaxval(context),
                                    badCount=self.getHystN(context),
                                    queueSize=self.getHystM(context),
                                    goodCount=self.getHystK(context),
                                    eventClass=self.eventClass,
                                    severity=self.severity,
                                    escalateCount=self.escalateCount)
        return mmt

    def getMinval(self, context):
        """Build the min value for this threshold.
        """
        minval = None
        if self.minval:
            try:
                express = "python:%s" % self.minval
                minval = talesEval(express, context)
            except:
                msg = (
                    "User-supplied Python expression (%s) for "
                    "minimum value caused error: %s"
                    ) % (self.minval,  self.dsnames)
                log.error(msg)
                raise pythonThresholdException(msg)
                minval = None
        return nanToNone(minval)

    def getMaxval(self, context):
        """Build the max value for this threshold.
        """
        maxval = None
        if self.maxval:
            try:
                express = "python:%s" % self.maxval
                maxval = talesEval(express, context)
            except:
                msg = (
                    "User-supplied Python expression (%s) for "
                    "maximum value caused error: %s"
                    ) % (self.maxval,  self.dsnames)
                log.error(msg)
                raise pythonThresholdException(msg)
                maxval = None
        return nanToNone(maxval)

    def getHystN(self, context):
        """
        """
        badCount = 0
        if self.badCount:
            try:
                express = "python:%s" % self.badCount
                badCount = talesEval(express, context)
            except:
                msg = (
                    "User-supplied Python expression (%s) for "
                    "hysteresis N value caused error: %s"
                    ) % (self.badCount,  self.dsnames)
                log.error(msg)
                raise pythonThresholdException(msg)
                badCount = 0
        return badCount

    def getHystM(self, context):
        """
        """
        queueSize = 0
        if self.queueSize:
            try:
                express = "python:%s" % self.queueSize
                queueSize = talesEval(express, context)
            except:
                msg = (
                    "User-supplied Python expression (%s) for "
                    "hysteresis M value caused error: %s"
                    ) % (self.queueSize,  self.dsnames)
                log.error(msg)
                raise pythonThresholdException(msg)
                queueSize = 0
        return queueSize

    def getHystK(self, context):
        """
        """
        goodCount = 0
        if self.goodCount:
            try:
                express = "python:%s" % self.goodCount
                goodCount = talesEval(express, context)
            except:
                msg = (
                    "User-supplied Python expression (%s) for "
                    "hysteresis K value caused error: %s"
                    ) % (self.goodCount,  self.dsnames)
                log.error(msg)
                raise pythonThresholdException(msg)
                goodCount = 0
        return goodCount


InitializeClass(HystThreshold)
HystThresholdClass = HystThreshold


class HystThresholdInstance(RRDThresholdInstance):
    # Not strictly necessary, but helps when restoring instances from
    # pickle files that were not constructed with a count member.
    count = {}
    hystCount = {}
    hystFlag = {}

    def __init__(self, id, context, dpNames,
                 minval, maxval, badCount, queueSize, goodCount,
                 eventClass, severity, escalateCount):
        RRDThresholdInstance.__init__(self, id, context, dpNames,
                                      eventClass, severity)
        self.count = {}
        self.hystCount = {}
        self.hystFlag = {}
        self.minimum = minval
        self.maximum = maxval
        self.badCount = badCount
        self.queueSize = queueSize
        self.goodCount = goodCount
        self.escalateCount = escalateCount

    def hystCountKey(self, dp):
        return self.context().deviceName + ':' + self.name() + ':' + dp

    def countKey(self, dp):
        return ':'.join(self.context().key()) + ':' + dp

    def saveHystState(self):
        log.debug("saving hysteresis state")
        atomicWrite(
            zenPath('var/%s_%s_hystCount.pickle' % (self.context().deviceName,
                                                    self.name())),
            pickle.dumps(self.hystCount),
            raiseException=False,
        )
        atomicWrite(
            zenPath('var/%s_%s_hystFlag.pickle' % (self.context().deviceName,
                                                   self.name())),
            pickle.dumps(self.hystFlag),
            raiseException=False,
        )

    def loadHystState(self):
        log.debug("Loading hyst state")
        try:
            self.hystCount = pickle.load(
                open(zenPath('var/%s_%s_hystCount.pickle' %
                     (self.context().deviceName, self.name()))))
            log.debug("restored %r", self.hystCount)
        except Exception:
            log.debug("error loading %s",
                      zenPath('var/%s_%s_hystCount.pickle' %
                              (self.context().deviceName, self.name())))
            pass
        try:
            self.hystFlag = pickle.load(
                open(zenPath('var/%s_%s_hystFlag.pickle' %
                     (self.context().deviceName, self.name()))))
            log.debug("restored %r", self.hystFlag)
        except Exception:
            log.debug("error loading %s",
                      zenPath('var/%s_%s_hystFlag.pickle' %
                              (self.context().deviceName, self.name())))
            pass

    def getHystCount(self, dp):
        countKey = self.hystCountKey(dp)
        if not countKey in self.hystCount:
            return 0
        return self.hystCount[countKey].count(1)

    def getCount(self, dp):
        countKey = self.countKey(dp)
        if not countKey in self.count:
            return None
        return self.count[countKey]

    def incrementCount(self, dp):
        countKey = self.countKey(dp)
        if not countKey in self.count:
            self.resetCount(dp)
        self.count[countKey] += 1
        return self.count[countKey]

    # bad is 1 for a bad  measurement and
    #        0 for a good measurement
    def incrementHystCount(self, dp, bad):
        self.loadHystState()

        # if start hysteresis is not set - just return 0
        if self.queueSize <= 0:
            return 0

        countKey = self.hystCountKey(dp)
        if not countKey in self.hystCount:
            self.resetHystCount(dp)
        self.hystCount[countKey].append(bad)
        self.saveHystState()
        if bad:
            return self.hystCount[countKey].count(bad)
        else:
            return list(self.hystCount[countKey])[-self.goodCount:].count(bad)

    def setHystFlag(self, dp, state):
        self.hystFlag[self.hystCountKey(dp)] = state
        self.saveHystState()

    def resetHystCount(self, dp):
        self.hystCount[self.hystCountKey(dp)] = deque(maxlen=self.queueSize)
        self.hystFlag[self.hystCountKey(dp)] = 0
        self.saveHystState()

    def resetCount(self, dp):
        self.count[self.countKey(dp)] = 0

    def checkRange(self, dp, value):
        'Check the value for min/max thresholds'
        log.debug(
            ("Checking %s %s against min %s, max %s, "
             "badCount '%s'('%s'), queueSize '%s', "
             "goodCount '%s',  hystKey %s"),
            dp, value, self.minimum, self.maximum, self.badCount,
            self.getHystCount(dp), self.queueSize,
            self.goodCount, self.hystCountKey(dp))
        if value is None:
            return []
        if isinstance(value, basestring):
            value = float(value)
        thresh = None

        # Handle all cases where both minimum and maximum are set.
        if self.maximum is not None and self.minimum is not None:
            if self.maximum >= self.minimum:
                if value > self.maximum:
                    thresh = self.maximum
                    how = 'exceeded'
                elif value < self.minimum:
                    thresh = self.minimum
                    how = 'not met'
            elif self.maximum < value < self.minimum:
                thresh = self.maximum
                how = 'violated'

        # Handle simple cases where only minimum or maximum is set.
        elif self.maximum is not None and value > self.maximum:
            thresh = self.maximum
            how = 'exceeded'
        elif self.minimum is not None and value < self.minimum:
            thresh = self.minimum
            how = 'not met'

        if thresh is not None:
            severity = 2  # self.severity
            hystCount = self.incrementHystCount(dp, 1)
            # if current hysteresis count at least reached
            # a limit of 'self.badCount'
            # restore original severity and mark a threshold as violated
            # begin event counting for escalation
            if (self.badCount - 1) < hystCount or \
                    self.hystFlag[self.hystCountKey(dp)] == 1:
                severity = self.severity
                count = self.incrementCount(dp)
                self.setHystFlag(dp, 1)
                if self.escalateCount and count >= self.escalateCount:
                    severity = min(severity + 1, 5)

            summary = 'threshold of %s %s: current value %f.' % (
                self.name(), how, float(value))
            evtdict = self._create_event_dict(value, summary, severity, how)
            if self.escalateCount:
                evtdict['escalation_count'] = count

            return self.processEvent(evtdict)
        else:
            hystCount = self.incrementHystCount(dp, 0)
            # if hysteresis didn't kick in propagate event further
            if self.hystFlag[self.hystCountKey(dp)] == 0:
                summary = 'threshold of %s restored: current value %f' % (
                    self.name(), value)
                self.resetCount(dp)
                return self.processClearEvent(
                    self._create_event_dict(value, summary, Event.Clear))
            else:
                #if hysteresis enabled wait till at least K clearing events
                if hystCount < self.goodCount:
                    return []
                else:
                    # at least K clearing events. Allow faster clearing
                    self.setHystFlag(dp, 0)
                    return self.processClearEvent(
                        self._create_event_dict(value, summary, Event.Clear))

    def _create_event_dict(self, current, summary, severity, how=None):
        event_dict = dict(device=self.context().deviceName,
                          summary=summary,
                          eventKey=self.id,
                          eventClass=self.eventClass,
                          component=self.context().componentName,
                          min=self.minimum,
                          max=self.maximum,
                          current=current,
                          severity=severity)
        deviceUrl = getattr(self.context(), "deviceUrl", None)
        if deviceUrl is not None:
            event_dict["zenoss.device.url"] = deviceUrl
        devicePath = getattr(self.context(), "devicePath", None)
        if devicePath is not None:
            event_dict["zenoss.device.path"] = devicePath
        if how is not None:
            event_dict['how'] = how
        return event_dict

    def processEvent(self, evt):
        """
        When a threshold condition is violated,
        pre-process it for (possibly) nicer
        formatting or more complicated logic.

        @paramater evt: event
        @type evt: dictionary
        @rtype: list of dictionaries
        """
        return [evt]

    def processClearEvent(self, evt):
        """
        When a threshold condition is restored,
        pre-process it for (possibly) nicer
        formatting or more complicated logic.

        @paramater evt: event
        @type evt: dictionary
        @rtype: list of dictionaries
        """
        return [evt]

    def raiseRPNExc(self):
        """
        Raise an RPN exception, taking care to log all details.
        """
        msg = "The following RPN exception is from user-supplied code."
        log.exception(msg)
        raise rpnThresholdException(msg)

    def getGraphElements(self, template, context, gopts, namespace, color,
                         legend, relatedGps):
        """Produce a visual indication on the graph of where the
        threshold applies."""
        unused(template, namespace)
        if not color.startswith('#'):
            color = '#%s' % color
        minval = self.minimum
        if minval is None:
            minval = NaN
        maxval = self.maximum
        if maxval is None:
            maxval = NaN
        hystval = self.hystval
        if hystval is None:
            hystval = NaN
        if not self.dataPointNames:
            return gopts
        gp = relatedGps[self.dataPointNames[0]]

        # Attempt any RPN expressions
        rpn = getattr(gp, 'rpn', None)
        if rpn:
            try:
                rpn = talesEvalStr(rpn, context)
            except:
                self.raiseRPNExc()
                return gopts

            try:
                minval = rpneval(minval, rpn)
            except:
                minval = 0
                self.raiseRPNExc()

            try:
                maxval = rpneval(maxval, rpn)
            except:
                maxval = 0
                self.raiseRPNExc()

        minstr = self.setPower(minval)
        maxstr = self.setPower(maxval)

        minval = nanToNone(minval)
        maxval = nanToNone(maxval)
        if legend:
            gopts.append(
                "HRULE:%s%s:%s\\j" % (minval or maxval, color, legend))
        elif minval is not None and maxval is not None:
            if minval == maxval:
                gopts.append(
                    "HRULE:%s%s:%s not equal to %s\\j" %
                    (minval, color, self.getNames(relatedGps), minstr))
            elif minval < maxval:
                gopts.append(
                    "HRULE:%s%s:%s not within %s and %s\\j" %
                    (minval, color, self.getNames(relatedGps), minstr, maxstr))
                gopts.append("HRULE:%s%s" % (maxval, color))
            elif minval > maxval:
                gopts.append(
                    "HRULE:%s%s:%s between %s and %s\\j" %
                    (minval, color, self.getNames(relatedGps), maxstr, minstr))
                gopts.append("HRULE:%s%s" % (maxval, color))
        elif minval is not None:
            gopts.append(
                "HRULE:%s%s:%s less than %s\\j" %
                (minval, color, self.getNames(relatedGps), minstr))
        elif maxval is not None:
            gopts.append(
                "HRULE:%s%s:%s greater than %s\\j" %
                (maxval, color, self.getNames(relatedGps), maxstr))

        return gopts

    def getNames(self, relatedGps):
        names = sorted(set(x.split('_', 1)[1] for x in self.dataPointNames))
        return ', '.join(names)

    def setPower(self, number):
        powers = ("k", "M", "G")
        if number < 1000:
            return number
        for power in powers:
            number = number / 1000.0
            if number < 1000:
                return "%0.2f%s" % (number, power)
        return "%.2f%s" % (number, powers[-1])

    def _checkImpl(self, dataPoint, value):
        return self.checkRange(dataPoint, value)

from twisted.spread import pb
pb.setUnjellyableForClass(HystThresholdInstance, HystThresholdInstance)
