from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.utils.formats import get_format
from django.contrib.admin.templatetags.admin_static import static
import os

STATUS_ICON_CLOCKED_IN = '<img src="%s" alt="%s" />' % (static('admin/img/icon_clock.gif'), _('clock running'))
HOURS_DISPLAY_DECIMALS = 2
WEEKDAY_FORMAT = 'D'

WORKING_DAYS_DEFAULT = (2, 3, 4, 5, 6) # 1=Sunday .. 7=Saturday
HOURS_PER_WEEK_DEFAULT = 40
DISPLAY_BALANCE_DEFAULT = True
DISPLAY_CLOSING_DEFAULT = False

DATE_FORMAT = getattr(settings, 'TIME_TRACKING_DATE_FORMAT', None) or get_format('DATE_FORMAT')
TIME_FORMAT = getattr(settings, 'TIME_TRACKING_TIME_FORMAT', None) or get_format('TIME_FORMAT')