# coding=utf-8
from time_tracking.settings import HOURS_DISPLAY_DECIMALS
from django.utils.translation import ungettext
from django import template
from django.template.defaultfilters import floatformat as django_floatformat

def floatformat(value, decimals):
    return django_floatformat(value, decimals).replace('-', u'−')

def hours(value, signed=False, decimals=HOURS_DISPLAY_DECIMALS, units=True):
    if not units:
        return floatformat(value, decimals)
    if not value:
        return ungettext('%s hour', '%s hours', 0) % floatformat(0, decimals)
    if abs(value) < 1:
        return ungettext('%s min', '%s min', value) % (('+' if signed and value > 0 else '') + floatformat(value * 60, decimals))
    return ungettext('%s hour', '%s hours', value) % (('+' if signed and value > 0 else '') + floatformat(value or 0, decimals))

def hours_decimal(value, decimals=HOURS_DISPLAY_DECIMALS):
    return hours(value, decimals=decimals, units=False)

def days(value):
    return ungettext('%s day', '%s days', value) % str(value)

register = template.Library()
register.filter('hours', hours)
register.filter('hours_decimal', hours_decimal)
register.filter('days', days)