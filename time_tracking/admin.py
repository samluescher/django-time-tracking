from time_tracking.forms import ClockForm
from time_tracking.templatetags import clockformats
from expenses.templatetags import moneyformats
from time_tracking.middleware import CurrentUserMiddleware
from time_tracking.models import Clock, Project, Activity, ClockOptions, ActivityOptions, TimeTrackingGroup
from django import forms
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _, ugettext
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


class ActivityAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'activity_type', 'time_factor')


class ClockOptionsAdmin(admin.ModelAdmin):
    list_display = ('username', 'display_balance', 'display_closing', 'hours_per_week', 'unpaid_break', 'weekday_1', 'weekday_2', 'weekday_3', 'weekday_4', 'weekday_5', 'weekday_6', 'weekday_7')


class ActivityOptionsAdmin(admin.ModelAdmin):
    list_display = ('activity', 'username', 'rate_formatted')

    def rate_formatted(self, obj):
        return moneyformats.money(obj.rate)
    rate_formatted.short_description = _('rate')
    rate_formatted.admin_order_field = 'rate'


class ClockInForm(forms.Form):
    
    def __init__(self, *args, **kwargs):
        super(ClockInForm, self).__init__(*args, **kwargs)
        # Field is added on __init__ due to current-user-related queryset 
        self.fields['project'] = forms.ModelChoiceField(label=_('Project'), 
            queryset=Project.get_queryset_for_current_user(), required=False)


class ClockAdmin(admin.ModelAdmin):
    date_hierarchy = 'start'
    list_display = ('status_icon', 'weekday', 'start_date', 'start_time', 'end_time', 'hours_rounded', 'hours_credited_rounded', 'activity', 'rate_formatted', 'cost_formatted', 'project', 'comment')
    list_display_links = ('status_icon', 'weekday', 'start_date',)
    form = ClockForm
    ordering = ['-start']

    if 'billing' in settings.INSTALLED_APPS:
        actions = ['bill_selected']

    def queryset(self, request):
        """
        Filter the objects displayed in the change_list to only
        display those for the currently signed in user.
        """
        qs = super(ClockAdmin, self).queryset(request)
        if not request.user.has_perm('time_tracking.can_set_user'):
            qs = qs.filter(user=request.user)
        return qs
        
    def bill_selected(self, request, queryset):
        from billing.models import ClockBill
        bill = ClockBill() 
        bill.save()
        if queryset.filter(bill=None).count() != queryset.count():
            self.message_user(request, _('Some entries were already billed and were not added to this bill.'))
        for obj in queryset.filter(bill=None):
            obj.bill = bill
            if not obj.billed_rate:
                obj.billed_rate = obj.get_rate() or 0
            if not obj.billed_time_factor:
                obj.billed_time_factor = obj.activity.time_factor
            obj.save()
        return HttpResponseRedirect(bill.get_admin_url())
    bill_selected.short_description = _('Create bill with selected %(verbose_name_plural)s')

    def add_view(self, request, form_url='', extra_context=None):
        if not request.user.has_perm('time_tracking.can_set_user'):
            self.exclude = ('user',)
        else:
            self.exclude = ()
        return super(ClockAdmin, self).add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, extra_context=None):
        if not request.user.has_perm('time_tracking.can_set_user'):
            self.exclude = ('user',)
        else:
            self.exclude = ()
            
        return super(ClockAdmin, self).change_view(request, object_id, extra_context)

    def test_view(self, request, extra_context=None):
        request.user.message_set.create(message="yay")
        return super(ClockAdmin, self).changelist_view(request, extra_context)

    def changelist_view(self, request, extra_context=None):
        if not request.user.has_perm('time_tracking.can_set_user'):
            if 'user' in self.list_display:
                list_display = list(self.list_display)
                list_display.remove('user')
                self.list_display = tuple(list_display)
            self.list_filter = ['start', 'project', 'activity']
        else:
            if 'user' not in self.list_display:
                self.list_display += ('user',)
            self.list_filter = ['start', 'project', 'activity', 'user']

        from django.contrib.admin.views.main import ChangeList
        cl = ChangeList(request, self.model, self.list_display, self.list_display_links,
            self.list_filter, self.date_hierarchy, self.search_fields,
            self.list_select_related, self.list_per_page, self.list_max_show_all, self.list_editable, self)
        clocked_in_time = Clock.clocked_in_time(request.user)
        if clocked_in_time and clocked_in_time.project:
            # TODO this is not working
            initial = {'project': clocked_in_time.project}
        else:
            initial = {'project': Project.get_latest_for_current_user()}
        extra_context = {
            'time_info': Clock.summarize(request.user, cl.query_set),
            'clock_in_form': ClockInForm(initial=initial),
        }
        
        return super(ClockAdmin, self).changelist_view(request, extra_context)

    def get_urls(self):
        from django.conf.urls.defaults import patterns, url
        urls = super(ClockAdmin, self).get_urls()
        url_patterns = patterns('',
            url(r'^in/$', self.admin_site.admin_view(self.clock_in), name="time_tracking_clock_in"),
            url(r'^out/$', self.admin_site.admin_view(self.clock_out), name="time_tracking_clock_out"),
        )
        url_patterns.extend(urls)
        return url_patterns
        
    def clock_in(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        else:
            clocked_in_time = Clock.clocked_in_time(request.user)
            project = None
            if request.method == 'POST':
                form = ClockInForm(request.POST)
                if not form.is_valid():
                    raise Exception(forms.ValidationError)
                if form.cleaned_data:
                    project = form.cleaned_data['project']
                else:
                    raise forms.ValidationError('Invalid project')
                
            can_clock_in = not clocked_in_time
            if clocked_in_time:
                if not project or clocked_in_time.project == project:
                    messages.add_message(request, messages.WARNING, _("Please clock out first. Clocked in: %s") % clocked_in_time.__unicode__())
                else:
                    clocked_in_time.clock_out()
                    messages.add_message(request, messages.SUCCESS, _("Clocked out: %s") % clocked_in_time.__unicode__())
                    can_clock_in = True
                
            if can_clock_in:
                try:
                    clock_in_time = Clock.clock_in(request.user, project)
                    if project:
                        messages.add_message(request, messages.SUCCESS, _("Clocked into %(project)s: %(clock)s") % 
                        {'clock': clock_in_time.__unicode__(), 'project': project.__unicode__()})
                    else:
                        messages.add_message(request, messages.SUCCESS, _("Clocked in: %(clock)s") % 
                            {'clock': clock_in_time.__unicode__()})
                except ValueError:
                    messages.add_message(request, messages.WARNING, _("In order to be able to clock in, you'll have to create a first entry."))

            return HttpResponseRedirect('../')

    def clock_out(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        else:
            clocked_in_time = Clock.clocked_in_time(request.user)
            if (clocked_in_time != None):
                clocked_in_time.clock_out()
                messages.add_message(request, messages.SUCCESS, _("Clocked out: %s") % clocked_in_time.__unicode__())
            else:
                messages.add_message(request, messages.WARNING, _("Please clock in first."))

            return HttpResponseRedirect('../')

    def cost_formatted(self, obj):
        return moneyformats.money(obj.get_cost())
    cost_formatted.short_description = _('cost')

    def rate_formatted(self, obj):
        return moneyformats.money(obj.get_rate())
    rate_formatted.short_description = _('rate')
        

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'group_names', 'status', 'budget_formatted', 'hours_sum_formatted', 'cost_sum_formatted', 'balance_formatted', 'coverage_formatted')

    def group_names(self, obj):
        return ', '.join([group.__unicode__() for group in obj.groups.all()])
    group_names.short_description = _('groups')

    def budget_formatted(self, obj):
        return moneyformats.money(obj.budget)
    budget_formatted.short_description = _('budget')
    budget_formatted.admin_order_field = 'budget'

    def hours_sum_formatted(self, obj):
        return clockformats.hours(obj.sum_hours(), units=False)
    hours_sum_formatted.short_description = _('hours spent')
    
    def cost_sum_formatted(self, obj):
        return moneyformats.money(obj.sum_cost())
    cost_sum_formatted.short_description = _('budget spent')

    def balance_formatted(self, obj):
        return moneyformats.money(obj.balance())
    balance_formatted.short_description = _('balance')
    
    def coverage_formatted(self, obj):
        return moneyformats.percent(obj.coverage())
    coverage_formatted.short_description = _('coverage')


class TimeTrackingGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_names', 'clock_sum')

    def user_names(self, obj):
        return ', '.join([user.__unicode__() for user in obj.user_set.all()])
    user_names.short_description = _('users')

    def clock_sum(self, obj):
        return ''
        #return money(Expense.objects.filter(expense_group=obj).aggregate(Sum('amount'))['amount__sum'])
    clock_sum.short_description = _('total')


admin.site.register(Clock, ClockAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(ClockOptions, ClockOptionsAdmin)
admin.site.register(ActivityOptions, ActivityOptionsAdmin)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(TimeTrackingGroup, TimeTrackingGroupAdmin)
