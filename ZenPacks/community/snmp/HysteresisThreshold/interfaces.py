from Products.Zuul.form import schema
from Products.Zuul.interfaces.component import IComponentInfo
from Products.Zuul.interfaces.template import IRRDDataSourceInfo

from Products.Zuul.interfaces import IInfo, IFacade
from Products.Zuul.interfaces.template import IThresholdInfo


# ZuulMessageFactory is the translation layer. You will see strings intended to
# been seen in the web interface wrapped in _t(). This is so that these strings
# can be automatically translated to other languages.
from Products.Zuul.utils import ZuulMessageFactory as _t

# In Zenoss 3 we mistakenly mapped TextLine to Zope's multi-line text
# equivalent and Text to Zope's single-line text equivalent. This was
# backwards so we flipped their meanings in Zenoss 4. The following block of
# code allows the ZenPack to work properly in Zenoss 3 and 4.

# Until backwards compatibility with Zenoss 3 is no longer desired for your
# ZenPack it is recommended that you use "SingleLineText" and "MultiLineText"
# instead of schema.TextLine or schema.Text.
from Products.ZenModel.ZVersion import VERSION as ZENOSS_VERSION
from Products.ZenUtils.Version import Version
if Version.parse('Zenoss %s' % ZENOSS_VERSION) >= Version.parse('Zenoss 4'):
    SingleLineText = schema.TextLine
    MultiLineText = schema.Text
else:
    SingleLineText = schema.Text
    MultiLineText = schema.TextLine


class IHystThresholdInfo(IThresholdInfo):
    """
    Adapts the HystThreshold Class
    """
    minval = schema.TextLine(title=_t(u'Minimum Value'), order=6)
    maxval = schema.TextLine(title=u'Maximum Value', order=7)
    badCount = schema.TextLine(
        title=u'An alert will be raised if N(Bad Measurements Count) \
                of M(Measurements Queue Size) measurements failed<br/> \
                Clear event will be generated only after \
                K(Good Measurements Count) sequential \
                clear measurements.<br> Bad Measurements Count',
        order=12, default=u"1")
    goodCount = schema.TextLine(
        title=u'Good Measurements Count', order=13, default=u"1")
    queueSize = schema.TextLine(
        title=u'Measurement Queue Size', order=14, default=u"1")
    escalateCount = schema.Int(title=_t(u'Escalate Count'), order=11)
