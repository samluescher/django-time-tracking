Django Time Tracking
====================

A simple Django Admin-based app for tracking working hours and creating time sheets.

Installation
------------

This document assumes that you are familiar with Python and Django.

1. Download and unzip the current release, or install using `git`:

        $ git clone git://github.com/philomat/django-time_tracking.git

2. Make sure `time_tracking` is on your `PYTHONPATH`.
3. Set up the database tables using 

	$ manage.py syncdb

4. Add `time_tracking.middleware.CurrentUserMiddleware` to your `MIDDLEWARE_CLASSES` setting, and make sure Django's `MessageMiddleware` is enabled as well:

        MIDDLEWARE_CLASSES = (
            ...
            'django.contrib.messages.middleware.MessageMiddleware',
            'time_tracking.middleware.CurrentUserMiddleware',
        )

5. Add `time_tracking` to your `INSTALLED_APPS` setting.

        INSTALLED_APPS = (
            ...
            'time_tracking',
        )
        
6. The app is now available in the Django Admin.

Missing features
----------------
  
* Billing