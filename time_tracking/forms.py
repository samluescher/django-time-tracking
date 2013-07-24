from time_tracking.models import Clock, Project
from time_tracking.middleware import CurrentUserMiddleware
from django.forms import ModelForm, ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

class ClockForm(ModelForm):
    
    class Meta:
        model = Clock

    def __init__(self, *args, **kwargs):
        if not 'initial' in kwargs:
            kwargs['initial'] = {}
        instance = kwargs.get('instance')
        if instance and instance.end:
            kwargs['initial'].update({'hours': None})
        super(ClockForm, self).__init__(*args, **kwargs)
    
    def clean(self):
        if 'user' in self.fields:
            user = self.cleaned_data.get('user', None)
        else:
            user = CurrentUserMiddleware.get_current_user()

        if user:
            # is `start` inside any between `start`/`end` of any other Clock entry?
            if 'start' in self.cleaned_data and self.cleaned_data['start']:
                overlap = Clock.objects.filter(start__lte=self.cleaned_data['start'], 
                    end__gt=self.cleaned_data['start'], user=user)
                if self.instance.pk:
                    overlap = overlap.exclude(pk=self.instance.pk)
                if overlap.count() > 0:
                    raise ValidationError(mark_safe(_('Start is overlapping with %s.') % overlap[0].get_admin_link()))

            # is `end` inside any between `start`/`end` of any other Clock entry?
            if 'end' in self.cleaned_data and self.cleaned_data['end']:
                overlap = Clock.objects.filter(start__lt=self.cleaned_data['end'], 
                    end__gte=self.cleaned_data['end'], user=user)
                if self.instance.pk:
                    overlap = overlap.exclude(pk=self.instance.pk)
                if overlap.count() > 0:
                    raise ValidationError(mark_safe(_('End is overlapping with %s.') % overlap[0].get_admin_link()))

            # is there any other Clock entry between `start`/`end`?
            if 'start' in self.cleaned_data and self.cleaned_data['start']and \
                'end' in self.cleaned_data and self.cleaned_data['end']:
                    overlap = Clock.objects.filter(start__gte=self.cleaned_data['start'], 
                        end__lte=self.cleaned_data['end'], user=user)
                    if self.instance.pk:
                        overlap = overlap.exclude(pk=self.instance.pk)
                    if overlap.count() > 0:
                        raise ValidationError(mark_safe(_('Start/end are overlapping with %s.') % overlap[0].get_admin_link()))

        if 'hours' in self.cleaned_data and self.cleaned_data['hours'] and 'end' in self.cleaned_data and self.cleaned_data['end']:
            raise ValidationError(_('Please enter either end or hours, but not both.'))

        return self.cleaned_data
    
    def clean_end(self):
        if 'end' in self.cleaned_data and self.cleaned_data['end'] and \
            'start' in self.cleaned_data and self.cleaned_data['start']:
                if self.cleaned_data['end'] <= self.cleaned_data['start']:
                    raise ValidationError(_('End must be later than start.'))

        return self.cleaned_data['end']
