import os
from wsgiref.simple_server import make_server
from django.core.wsgi import get_wsgi_application

os.environ['DATABASE_URL'] = ''
os.environ['SQLITE_NAME'] = r'scratch\fly_school_system.db'
os.environ['DEBUG'] = 'True'
os.environ['SECURE_SSL_REDIRECT'] = 'False'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_system_django.settings')

app = get_wsgi_application()
print('Serving on http://127.0.0.1:8005/ sqlite=' + os.environ['SQLITE_NAME'], flush=True)
make_server('127.0.0.1', 8005, app).serve_forever()
