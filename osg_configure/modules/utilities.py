#!/usr/bin/python

""" Module to hold various utility functions """

import re, socket, os, types, pwd, sys, glob, ConfigParser, stat
import tempfile, subprocess, rpm

from osg_configure.modules import exceptions
from osg_configure.modules import validation

__all__ = ['using_prima',
           'get_vos',
           'enable_service',
           'disable_service',
           'service_enabled',    
           'get_elements',
           'get_hostname',
           'get_set_membership',
           'blank',
           'create_map_file',
           'fetch_crl',
           'ce_installed',
           'atomic_write']
  
CONFIG_DIRECTORY = "/etc/osg"

  
      
def get_elements(element=None, filename=None):
  """Get values for selected element from xml file specified in filename"""
  if filename is None or element is None:
    return []
  import xml.dom.minidom
  try:
    dom = xml.dom.minidom.parse(filename)
  except IOError:
    return []
  except xml.parsers.expat.ExpatError:
    return []
  values = dom.getElementsByTagName(element)
  return values
    
def write_attribute_file(filename=None, attributes=None):
  """
  Write attributes to osg attributes file in an atomic fashion
  """
  
  if attributes is None:
    attributes = {}
    
  if filename is None:
    return True
    
  variable_string = ""
  export_string = ""
  # keep a list of array variables 
  array_vars = {}
  keys = attributes.keys()
  keys.sort()
  for key in keys:
    if type(attributes[key]) is types.ListType:
      for item in attributes[key]:
        variable_string += "%s=\"%s\"\n" % (key, item)
    else:  
      variable_string += "%s=\"%s\"\n" % (key, attributes[key])
    if len(key.split('[')) > 1:
      real_key = key.split('[')[0]
      if real_key not in array_vars:
        export_string += "export %s\n" % key.split('[')[0]
        array_vars[real_key] = ""
    else:
      export_string += "export %s\n" % key
       
  file_contents = "#!/bin/sh\n"
  file_contents += "#---------- This file automatically generated by "
  file_contents += "osg-configure\n"
  file_contents += "#---------- This is periodically overwritten.  " 
  file_contents += "DO NOT HAND EDIT\n"
  file_contents += "#---------- Instead, write any environment variable " 
  file_contents += "customizations into\n"
  file_contents += "#---------- the config.ini [Local Settings] section, " 
  file_contents += "as documented here:\n"
  file_contents += "#---------- https://twiki.grid.iu.edu/bin/view/Release"
  file_contents += "Documentation/ConfigurationFileLocalSettings\n"
  file_contents += "#---  variables -----\n"
  file_contents += variable_string
  file_contents += "#--- export variables -----\n"
  file_contents += export_string
  atomic_write(filename, file_contents, mode=0644)
  return True

def get_set_membership(test_set, reference_set, defaults = None):
  """
  See if test_set has any elements that aren't keys of the reference_set 
  or optionally defaults.  Takes lists as arguments
  """
  missing_members = []
  
  if defaults is None:
    defaults = []
  for member in test_set:
    if member not in reference_set and member not in defaults:
      missing_members.append(member)
  return missing_members

def get_hostname():
  """Returns the hostname of the current system"""
  try:
    return socket.gethostbyaddr(socket.gethostname())[0]
  # pylint: disable-msg=W0703
  except Exception:
    return None
  return None

def blank(value):
  """Check the value to check to see if it is 'UNAVAILABLE' or blank, return True 
  if that's the case
  """
  if type(value) != types.StringType:
    if value is None:
      return True
    return False
  
  if (value.upper().startswith('UNAVAILABLE') or
      value.upper() == 'DEFAULT' or
      value == "" or
      value is None):
    return True
  return False

def get_vos(user_vo_file):
  """
  Returns a list of valid VO names.
  """

  if (user_vo_file is None or 
      not os.path.isfile(user_vo_file)):
    user_vo_file = os.path.join(os.path.join(CONFIG_DIRECTORY, 
                                             'osg-user-vo-map.txt'))
  if not os.path.isfile(user_vo_file):
    return []
  file_buffer = open(os.path.expandvars(user_vo_file), 'r')
  vo_list = []
  for line in file_buffer:
    try:
      line = line.strip()
      if line.startswith("#"):
        continue
      vo = line.split()[1]
      if vo.startswith('us'):
        vo = vo[2:]
      if vo not in vo_list:
        vo_list.append(vo)
    except (KeyboardInterrupt, SystemExit):
      raise
    except:
      pass
  return vo_list

def service_enabled(service_name):
  """
  Check to see if a service is enabled
  """
  if service_name == None or service_name == "":
    return False
  process = subprocess.Popen(['/sbin/service', '--list', service_name], 
                             stdout=subprocess.PIPE)
  output = process.communicate()[0]
  if process.returncode != 0:
    return False  

  match = re.search(service_name + '\s*\|.*\|\s*([a-z ]*)$', output)
  if match:
    # The regex above captures trailing whitespace, so remove it
    # before we make the comparison. -Scot Kronenfeld 2010-10-08
    if match.group(1).strip() == 'enable':
      return True
    else:
      return False
  else:
    return False 
  
def create_map_file(using_gums = False):
  """
  Check and create a mapfile if needed
  """

  map_file = os.path.join('/',
                          'var',
                          'lib',
                          'osg',
                          'osg-user-vo-map')
  result = True
  try:
    if validation.valid_user_vo_file(map_file):
      return result
    if using_gums:
      gums_script = os.path.join('/',
                                 'usr',
                                 'bin',
                                 'gums-host-cron')
    else:
      gums_script = os.path.join('/',
                                 'usr'
                                 'bin',
                                 'edg-mkgridmap')
      
    sys.stdout.write("Running %s, this process may take some time " % gums_script +
                     "to query vo and gums servers\n")
    sys.stdout.flush()
    if not run_script([gums_script]):
      return False    
  except IOError:
    result = False
  return result

def fetch_crl():
  """
  Run fetch_crl script and return a boolean indicating whether it was successful
  """

  try:
    crl_files = glob.glob(os.path.join('/', 
                                       'etc', 
                                       'grid-security', 
                                       'certificates', 
                                       '*.r0'))
    if len(crl_files) > 0:
      sys.stdout.write("CRLs exist, skipping fetch-crl invocation\n")
      sys.stdout.flush()
      return True
      
    crl_path = os.path.join('/',
                            'usr',
                            'sbin',
                            'fetch-crl')
                 
    if not validation.valid_file(crl_path):
      sys.stdout.write("Can't find fetch-crl script, skipping fetch-crl invocation\n")
      sys.stdout.flush()
      return True
    
    sys.stdout.write("Running %s, this process make take " % crl_path +
                     "some time to fetch all the crl updates\n")
    sys.stdout.flush()
    if not run_script([crl_path]):
      return False
  except IOError:
    return False
  return True

def run_script(script):
  """
  Arguments:
  script - a string or a list of arguments to run formatted while 
           the args argument to subprocess.Popen
  
  Returns:
  True if script runs successfully, False otherwise
  """
  
  if not validation.valid_executable(script[0]):
    return False

  process = subprocess.Popen(script)
  process.communicate()
  if process.returncode != 0:
    return False
    
  return True          


def get_condor_location(default_location = '/usr'):
  """
  Check environment variables to try to get condor location
  """

  if 'CONDOR_LOCATION' in os.environ:
    return os.path.normpath(os.environ['CONDOR_LOCATION'])  
  elif not blank(default_location):
    return default_location
  else:
    return ""

def get_condor_config(default_config = '/etc/condor'):
  """
  Check environment variables to try to get condor config
  """
  
  if 'CONDOR_CONFIG' in os.environ:
    return os.path.normpath(os.environ['CONDOR_CONFIG'])
  elif not blank(default_config):
    return os.path.normpath(default_config)
  else:
    return os.path.join(get_condor_location(),
                        'etc',
                        'condor_config')

def atomic_write(filename = None, contents = None, **kwargs):
  """
  Atomically write contents to a file
  
  Arguments:
  filename - name of the file that needs to be written
  contents - string with contents to write to file

  Keyword arguments:
  mode - permissions for the file, if set to None the previous 
         permissions will be preserved
  
  Returns:
  True if file has successfully been written, False otherwise
  
  """

  if (filename is None or contents is None):
    return True
   
  try:
    (config_fd, temp_name) = tempfile.mkstemp(dir=os.path.dirname(filename))
    mode = kwargs.get('mode', None)
    if mode is None:
        if validation.valid_file(filename):
          mode = stat.S_IMODE(os.stat(filename).st_mode)
        else:
          # give file 0644 permissions by default 
          mode = 420
    try:
      try:
        os.write(config_fd, contents)
      finally:
        os.close(config_fd)
    except:
      os.unlink(temp_name)
      raise 
    os.rename(temp_name, filename)
    os.chmod(filename, mode)
  except Exception, e:
    return False
  return True


def ce_installed():
  """
  Check to see if the osg-ce metapackage is installed
  
  Returns:
  True if osg-ce metapackage rpm is installed, False otherwise
  """
  ts = rpm.TransactionSet()
  if ts.dbMatch('name', 'osg-ce').count() == 1:
    return True
  return False
