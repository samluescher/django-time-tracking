# coding=utf-8
from time_tracking.middleware import CurrentUserMiddleware
from time_tracking.settings import *
from django.db import models
from django.contrib.auth.models import User, Group
from django.utils.translation import ugettext_lazy as _, ugettext
from django.conf import settings
from django.template.defaultfilters import date as format_date, time as format_time
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.core.exceptions import ValidationError
import datetime


if not 'time_tracking.middleware.CurrentUserMiddleware' in settings.MIDDLEWARE_CLASSES:
    raise ImproperlyConfigured('Please add `time_tracking.middleware.CurrentUserMiddleware` to your `MIDDLEWARE_CLASSES` setting.')


from django.db.models import Q
import datetime

DATE_FORMAT = get_format('DATE_FORMAT')
SUNDAY = datetime.date(2010, 7, 18) # is a Sunday


class TimeTrackingGroup(Group):

    class Meta:
        proxy = True
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')
    
    @staticmethod
    def get_default():
        try:
            return CurrentUserMiddleware.get_current_user_groups()[0]
        except IndexError:
            return None
            
    @staticmethod
    def get_allowed_for_current_user():
        if not CurrentUserMiddleware.get_current_user().is_superuser:
            groups = CurrentUserMiddleware.get_current_user_groups()
        else:
            groups = Group.objects.all()
        return [group.pk for group in groups]


class GroupAllowedForCurrentUserManager(models.Manager):
    """
    Filters the QuerySet so that the current user can only see objects that were
    assigned a group that the current user belongs to. 
    """

    def get_query_set(self):
        qs = super(GroupAllowedForCurrentUserManager, self).get_query_set()
        if not CurrentUserMiddleware.get_current_user().is_superuser:
            qs = qs.filter(groups__pk__in=TimeTrackingGroup.get_allowed_for_current_user())
        return qs


class Activity(models.Model):
    
    WORK = 100
    PAID_LEAVE = 200
    UNPAID_LEAVE = 300
    
    name = models.CharField(_('name'), max_length=255)
    activity_type = models.IntegerField(_('type'), choices=((WORK, _('work')), (PAID_LEAVE, _('paid leave')), (UNPAID_LEAVE, _('unpaid leave'))), default=WORK)
    time_factor = models.FloatField(_('temporal factor'), default=1)

    _('work')
    _('leave')
    _('paid leave')
    _('unpaid leave')
    _('sick leave')
    _('holidays')
    _('compensatory time')

    class Meta:
        ordering = ['activity_type', 'name']
        verbose_name = _('activity')
        verbose_name_plural = _('activities')

    @staticmethod
    def get_default():
        return Activity.objects.filter(activity_type=Activity.WORK)[0]

    @staticmethod
    def get_latest_for_current_user():
        return Clock.get_latest_value('activity', include_null=False)

    def __unicode__(self):
        return ugettext(self.name)

    def get_options(self, for_user=None):
        return ActivityOptions.get_for_activity(activity=self, for_user=for_user)

    def get_rate(self, for_user=None):
        try:
            opts = self.get_options(for_user)
            return opts.rate
        except ActivityOptions.DoesNotExist:
            pass


class Project(models.Model):
    
    ACTIVE = 100
    COMPLETED = 500
    
    name = models.CharField(_('name'), max_length=255)
    budget = models.DecimalField(_('budget'), max_digits=12, decimal_places=2, null=True, blank=True)
    groups = models.ManyToManyField(TimeTrackingGroup, limit_choices_to={'pk__in': TimeTrackingGroup.get_allowed_for_current_user})
    status = models.IntegerField(_('status'), default=ACTIVE, choices=((ACTIVE, _('active')), (COMPLETED, _('completed'))))

    class Meta:
        ordering = ['name']
        verbose_name = _('project')
        verbose_name_plural = _('projects')

    objects = GroupAllowedForCurrentUserManager()

    def __unicode__(self):
        return self.name

    @staticmethod
    def get_queryset_for_current_user():
        return Project.objects.filter(status__lt=Project.COMPLETED)

    @staticmethod
    def get_pk_for_current_user():
        return [project.pk for project in Project.get_queryset_for_current_user()]
        
    @staticmethod
    def get_latest_for_current_user():
        return Clock.get_latest_value('project', include_null=True)

    def sum_hours(self):
        return Clock.sum_hours(Clock.objects.filter(project=self))
    sum_hours.short_description = _('hours spent')

    def sum_cost(self):
        return Clock.sum_cost(Clock.objects.filter(project=self))
    sum_cost.short_description = _('budget spent')

    def balance(self):
        cost_sum = self.sum_cost()
        if self.budget > 0 and cost_sum > 0:
            return float(self.budget) - cost_sum
    balance.short_description = _('balance')

    def coverage(self):
        balance = self.balance()
        if balance != None:
            return balance / float(self.budget)
    coverage.short_description = _('coverage')


def validate_null_unique(value):
    # TODO is not working
    if not value:
        raise ValidationError(u'%s blarz' % value)
        existing = ClockOptions.objects.filter(user=None)
        if self.pk:
            existing = existing.exclude(pk=self.pk)
        if existing.exists():
            raise ValidationError(u'%s blarz' % value)


class AbstractUserOptions(models.Model):

    class Meta:
        abstract = True
        ordering = ['user']

    def username(self):
        if self.user:
            return self.user.username
        else:
            return ugettext('all users')
    username.short_description = _('user')

    def __unicode__(self):
        return self.username()

    @classmethod
    def get_for_user(klass, for_user=None, qs=None):
        """
        Returns model instance for specific user (if omitted, instance for current user is returned).
        If no specific instance exists, default instance for all users is returned.
        """
        if qs is None:
            qs = klass.objects.all()
        try:
            if not for_user:
                for_user = CurrentUserMiddleware.get_current_user()
            return qs.filter(user=for_user)[0]
        except IndexError:
            try:
                return qs.filter(user=None)[0]
            except IndexError:
                raise klass.DoesNotExist()


class ActivityOptions(AbstractUserOptions):

    user = models.ForeignKey(User, verbose_name=_('user'), null=True, blank=True)
    activity = models.ForeignKey(Activity, verbose_name=_('activity'), null=False, blank=False)
    rate = models.DecimalField(_('hourly rate'), max_digits=10, decimal_places=2, null=False, blank=False)

    class Meta:
        verbose_name = _('rate')
        verbose_name_plural = _('rates')

    @classmethod
    def get_for_activity(klass, activity, for_user=None, qs=None):
        if qs is None:
            qs = klass.objects.all()
        qs = qs.filter(activity=activity)
        return klass.get_for_user(for_user=for_user, qs=qs)


class ClockOptions(AbstractUserOptions):
    # todo: Prevent deleting default object (user==None)

    user = models.ForeignKey(User, verbose_name=_('user'), unique=True, null=True, blank=True, validators=[validate_null_unique])
    display_balance = models.BooleanField(_('display balance'), default=DISPLAY_BALANCE_DEFAULT)
    display_closing = models.BooleanField(_('display closing time'), default=DISPLAY_CLOSING_DEFAULT)
    hours_per_week = models.FloatField(_('hours per week'), default=HOURS_PER_WEEK_DEFAULT, help_text=('Hours as a decimal number'), validators=[models.validators.MinValueValidator(0)])
    unpaid_break = models.FloatField(_('unpaid break'), default=0, help_text=('Hours as a decimal number. This is for projecting closing times.'), validators=[models.validators.MinValueValidator(0)])

    @property
    def hours_per_day(self):
        days = len(self.working_days)
        if days > 0:
            return self.hours_per_week / float(len(self.working_days))
        else:
            return None

    class Meta:
        verbose_name = _('clock options')
        verbose_name_plural = _('clock options')

    @staticmethod
    def contribute_working_days_fields():
        date = SUNDAY
        for weekday in range(1, 8):
            attname = 'weekday_%i' % weekday
            field = models.BooleanField(format_date(date, WEEKDAY_FORMAT), default=weekday in WORKING_DAYS_DEFAULT)
            field.contribute_to_class(ClockOptions, attname)
            date += datetime.timedelta(days=1)

    def get_working_days(self):
        date = SUNDAY
        working_days = []
        for weekday in range(1, 8):
            attname = 'weekday_%i' % weekday
            if getattr(self, attname, False):
                working_days.append(weekday)
        return working_days
        
    def set_working_days(self, working_days):
        for weekday in range(1, 8):
            attname = 'weekday_%i' % weekday
            setattr(self, attname, weekday in working_days)
    
    working_days = property(get_working_days, set_working_days)

    def working_days_formatted(self):
        result = ''
        for weekday in self.working_days:
            if result != '':
                result += ', ' 
            result += format_date(SUNDAY + datetime.timedelta(days=weekday - 1), WEEKDAY_FORMAT)
        return result
    working_days_formatted.short_description = _('working days')
            
ClockOptions.contribute_working_days_fields()


class Clock(models.Model):
    # todo: Move validation from form to model so that it also works with clocking in / out
    # todo: Clearing end should reset hours
    # todo: test with no entries / only one entry etc
    # todo: Balance is incorrect for compensatory time: Target time is raised during such absences, which is wrong since it has already been delivered

    start = models.DateTimeField(_('start'), default=datetime.datetime.today)
    end = models.DateTimeField(_('end'), null=True, blank=True)
    user = models.ForeignKey(User, verbose_name=_('user'), default=CurrentUserMiddleware.get_current_user)
    activity = models.ForeignKey(Activity, verbose_name=_('activity'), default=Activity.get_latest_for_current_user)
    hours = models.FloatField(_('hours'), blank=True, null=True, validators=[models.validators.MinValueValidator(0)])
    project = models.ForeignKey(Project, blank=True, null=True, verbose_name=_('project'), default=Project.get_latest_for_current_user, limit_choices_to={'pk__in': Project.get_pk_for_current_user})
    comment = models.TextField(_('comment'), blank=True, default='')
    
    billed_rate = models.DecimalField(_('billed rate'), max_digits=10, decimal_places=2, null=True, blank=True, editable=False)
    billed_time_factor = models.FloatField(_('billed temporal factor'), null=True, blank=True, editable=False)
    # currently unused, but would be handy for clock entries when actual hours and billable hours differ:
    billed_hours = models.FloatField(_('billable hours'), blank=True, null=True, validators=[models.validators.MinValueValidator(0)], editable=False)
    if 'billing' in settings.INSTALLED_APPS:
        from billing.models import ClockBill
        bill = models.ForeignKey(ClockBill, verbose_name=_('bill'), editable=False, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['start']
        verbose_name = _('clock entry')
        verbose_name_plural = _('clock entries')
        permissions = (
            ('can_set_user', ugettext('can set user')),
        )
        
    def get_admin_url(self):
        return reverse('admin:time_tracking_clock_change', args=(self.pk,));

    def get_admin_link(self):
        return mark_safe(u'%s: <a href="%s">%s</a>' % 
            (capfirst(self._meta.verbose_name), self.get_admin_url(), self.__unicode__()))

    @staticmethod
    def clocked_in_time(user):
        try:
            time = Clock.objects.filter(user=user
                ).order_by('-start'
                ).filter(end__isnull=True)[:1].get()
        except:
            time = None
        return time

    def clock_out(self):
        self.end = datetime.datetime.now()
        self.save()

    @staticmethod
    def clock_in(user, project=None):
        clock_in_time = Clock()
        clock_in_time.start = datetime.datetime.now()
        clock_in_time.end = None
        clock_in_time.user = user
        clock_in_time.project = project
        clock_in_time.save()
        return clock_in_time

    def save(self):
        user = None
        try:
            user = self.user
        except (User.DoesNotExist):
            pass
        if not user:
            self.user = CurrentUserMiddleware.get_current_user()
        if self.end and not self.hours:
            self.hours = Clock.hours_between(self.start, self.end)
        if self.hours and not self.end:
            self.end = self.start + datetime.timedelta(hours=self.hours)
        super(Clock, self).save()

    @staticmethod
    def get_latest_value(field, for_user=None, include_null=True):
        try:
            if not for_user:
                for_user = CurrentUserMiddleware.get_current_user()
            entries = Clock.objects.filter(user=for_user)
            if not include_null:
                entries = entries.exclude(**{field: None})
            return getattr(entries.latest('start'), field)
        except Clock.DoesNotExist:
            return None

    @staticmethod
    def django_week_day(date):
        """ returns 1 for Sunday .. 7 for Saturday, as Django QuerySet <field>__week_day would """
        # see http://code.djangoproject.com/ticket/7672#comment:3
        return date.isoweekday() % 7 + 1

    @staticmethod
    def sum_working_days(start, end):
        test_date = datetime.datetime(start.year, start.month, start.day, 0, 0, 0)
        end_date = datetime.datetime(end.year, end.month, end.day, 0, 0, 0)
        working_days_total = 0
        working_days = ClockOptions.get_for_user().working_days
        while (test_date <= end_date):
            if Clock.django_week_day(test_date) in working_days:
                working_days_total += 1
            test_date += datetime.timedelta(days=1)
        return working_days_total

    @staticmethod
    def filter_between(qs, from_date=None, to_date=None):
        if from_date:
            qs = qs.filter(start__gte=from_date)
        if to_date:
            qs = qs.filter(models.Q(end__lte=to_date) | models.Q(start__lte=to_date))
        return qs
        
    @staticmethod
    def sum_hours(qs, from_date=None, to_date=None):
        times = Clock.filter_between(qs, from_date, to_date).exclude(hours=None)
        distinct_time_factors = times.values('activity__time_factor').annotate(count=models.Count('pk'))
        hours_sum = 0
        for item in distinct_time_factors:
            factor = item['activity__time_factor']
            hours_sum += times.filter(activity__time_factor=factor).aggregate(models.Sum('hours'))['hours__sum'] * factor
        return hours_sum

    @staticmethod
    def sum_cost(qs, from_date=None, to_date=None):
        # TODO Optimize this method with fewer queries
        times = Clock.filter_between(qs, from_date, to_date).exclude(hours=None)
        distinct_activities = times.values('activity').annotate(count=models.Count('pk'))
        cost_sum = 0
        # for each activity:
        for item in distinct_activities:
            activity = Activity.objects.get(pk=item['activity'])
            hours_sum_per_user = times.filter(activity=activity).values('user').annotate(models.Sum('hours'))
            # sum hours per user and multiply by user's rate for activity 
            for hours_sum in hours_sum_per_user:
                cost = Clock.calc_cost(hours_sum['user'], activity, hours_sum['hours__sum'])
                if cost:
                    cost_sum += cost
            
            # sum hours and multiply by rate for activity (replaced since users can now have individual rates)
            # hours_sum = times.filter(activity=activity).aggregate(models.Sum('hours'))['hours__sum']
            # rate = activity.get_rate()
            # if rate:
            #    cost_sum += hours_sum * float(activity.time_factor) * float(rate)

        return cost_sum

    @staticmethod
    def calc_cost(user, activity, hours_sum, billed_rate=None, billed_time_factor=None):
        if not hours_sum:
            return None
        if billed_rate is None:
            billed_rate = activity.get_rate(for_user=user)
        if billed_time_factor is None:
            billed_time_factor = activity.time_factor
        if billed_rate:
            return hours_sum * float(billed_time_factor) * float(billed_rate)

    @staticmethod
    def sum_breaks(qs, from_date, to_date):
        times = Clock.filter_between(qs, from_date, to_date).order_by('start')
        seconds = 0
        i = len(times) - 1
        while i > 0:
            if times[i-1].end:
                seconds += (times[i].start - times[i-1].end).seconds
            i -= 1
        return seconds / 3600.0

    @staticmethod
    def count_days(qs, from_date, to_date):
        times = Clock.filter_between(qs, from_date, to_date)
        # This is not working since aggregation does not work with extra() fields:
        #     from django.db.models import Count
        #     return times.extra(select={'date_only': "DATE(start)"}).aggregate(Count('start_date', distinct=True))['date_only__count']
        # However, this is much simpler anyway:
        return times.dates('start', 'day').count()

    @staticmethod
    def start_of_week(date):
        days_left_for_week = Clock.django_week_day(date) - sorted(ClockOptions.get_for_user().working_days).pop(0)
        return date - datetime.timedelta(days=days_left_for_week)

    @staticmethod
    def end_of_week(date):
        days_left_for_week = sorted(ClockOptions.get_for_user().working_days).pop() - Clock.django_week_day(date)
        return date + datetime.timedelta(days=days_left_for_week)

    @staticmethod
    def start_of_day(date):
        return datetime.datetime(date.year, date.month, date.day)
    
    @staticmethod
    def summarize(user, qs):
        # TODO: Meaning of summary is unclear to superuser (i.e. if multiple usersa are displayed)
        from django.db.models import Min, Max
        times = qs.filter(user=user)
        summary = times.aggregate(from_start=Min('start'), to_start=Max('start'), to_end=Max('end'))
        from_start = summary['from_start']
        to_start = summary['to_start']
        to_end = summary['to_end']
        clock_options = ClockOptions.get_for_user(user)
        
        if not from_start or not to_start or not to_end:
            working_days = working_days_week = days_actual = hours_actual = hours_today = break_today = projected_break = 0
        else:
            working_days = Clock.sum_working_days(from_start, to_start)
            working_days_week = Clock.sum_working_days(Clock.start_of_week(from_start), Clock.end_of_week(to_start))
            days_actual = Clock.count_days(qs, from_start, max(to_start, to_end))
            hours_actual = Clock.sum_hours(qs, from_start, max(to_start, to_end))
            today = Clock.start_of_day(datetime.datetime.today())
            hours_today = Clock.sum_hours(qs, today, today + datetime.timedelta(days=1)) or 0
            break_today = Clock.sum_breaks(qs, today, today + datetime.timedelta(days=1))
            if not break_today: 
                projected_break = clock_options.unpaid_break
            else:
                projected_break = 0
        
        hours_target = working_days * clock_options.hours_per_day
        clocked_in_time = Clock.clocked_in_time(user)
        
        # User is currently clocked in: Add hours until now
        hours_counting = 0
        max_clocked_in_time = Clock.start_of_day(to_start or datetime.datetime.now()) + datetime.timedelta(days=1)
        if from_start and clocked_in_time != None and clocked_in_time.start >= from_start and clocked_in_time.start < max_clocked_in_time:
            to_start = to_end = datetime.datetime.now()
            hours_counting = Clock.hours_between(clocked_in_time.start, to_start)
            hours_actual += hours_counting
            hours_today += hours_counting
        balance = hours_actual - hours_target
        
        summary = {
            'clock_options': clock_options,
            'hours': {
                'balance': balance,
                'balance_until_weekend': hours_actual - working_days_week * clock_options.hours_per_day,
                'target': working_days * clock_options.hours_per_day,
                'actual': hours_actual,
                'today': hours_today,
                'counting': hours_counting,
                'weekly_target': clock_options.hours_per_week,
                'average_daily': hours_actual / float(days_actual) if days_actual != 0 else 0,
                'closing': {
                    'regular': datetime.datetime.now() - datetime.timedelta(hours=hours_today - clock_options.hours_per_day) + datetime.timedelta(hours=projected_break),
                    'adjusted': datetime.datetime.now() - datetime.timedelta(hours=balance) + datetime.timedelta(hours=projected_break),
                },
                'break_today': break_today or clock_options.unpaid_break,
            },
            'days': {
                'target': working_days,
                'actual': days_actual,
            },
            'dates': {
                'today': datetime.datetime.today(),
                'from': from_start,
                'to': to_end
            },
            'projects': Project.objects.filter(pk__in=times.values('project')),
        }
        
        if 'billing' in settings.INSTALLED_APPS:
            summary.update({
                'cost': {
                    'total': Clock.sum_cost(times),
                    'unbilled': Clock.sum_cost(times.filter(bill=None))
                },
            })
        return summary
        
    def get_rate(self):
        if self.billed_rate:
            return self.billed_rate
        return self.activity.get_rate(for_user=self.user)
    get_rate.short_description = _('rate')

    def get_cost(self):
        return Clock.calc_cost(self.user, self.activity, self.hours, 
            self.billed_rate, self.billed_time_factor)
    get_cost.short_description = _('cost')
        
    def hours_rounded(self):
        if self.hours != None:
            return round(self.hours, HOURS_DISPLAY_DECIMALS)
        else:
            return None
    hours_rounded.short_description = _('duration')

    def hours_credited(self):
        if self.hours != None:
            return self.hours * self.activity.time_factor
        else:
            return None
    hours_credited.short_description = _('hours')

    def hours_credited_rounded(self):
        if self.hours != None:
            return round(self.hours_credited(), HOURS_DISPLAY_DECIMALS)
        else:
            return None
    hours_credited_rounded.short_description = _('hours')
    
    @staticmethod
    def hours_between(start, end):
        if end != None:
            delta = (end - start)
            return delta.days * 24 + delta.seconds / 3600.0
        else:
            return None

    def status_icon(self):
        if self.end is None and self.hours is None:
            return STATUS_ICON_CLOCKED_IN
        else:
            return ''
    status_icon.short_description = ''
    status_icon.allow_tags = True

    def weekday(self):
        return format_date(self.start, WEEKDAY_FORMAT)
    weekday.short_description = _('day')
        
    def start_date(self):
        return format_date(self.start, DATE_FORMAT)
    start_date.short_description = _('date')
    start_date.admin_order_field = 'start'

    def end_date(self):
        return format_date(self.end, DATE_FORMAT)
    end_date.short_description = _('end date')
    end_date.admin_order_field = 'end'

    def start_time(self):
        return format_time(self.start, TIME_FORMAT)
    start_time.short_description = _('start')

    def end_time(self):
        if self.end != None:
            if self.start_date() == self.end_date():
                return format_time(self.end, TIME_FORMAT)
            else:
                return '%(time)s (%(date)s)' % {'time': format_time(self.end, TIME_FORMAT), 'date': self.end_date()}
        else:
            return ''
    end_time.short_description = _('end')
    
    def __unicode__(self):
        return u'%(from_date)s %(from_time)s–%(to_time)s' % {
            'from_date': self.start_date(),
            'from_time': self.start_time(),
            'to_time': self.end_time(),
        }

        return result