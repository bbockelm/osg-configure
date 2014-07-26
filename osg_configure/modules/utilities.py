""" Module to hold various utility functions """

import re
import socket
import os
import types
import sys
import glob
import stat
import tempfile
import subprocess
import rpm
import platform

from osg_configure.modules import validation

__all__ = ['get_elements',
           'write_attribute_file',
           'get_set_membership',
           'get_hostname',
           'blank',
           'get_vos',
           'service_enabled',
           'create_map_file',    
           'fetch_crl',
           'run_script',
           'get_condor_location',
           'get_condor_config',
           'get_condor_config_val'
           'atomic_write',
           'ce_installed',
           'any_rpms_installed'
           'rpm_installed',           
           'get_test_config',
           'make_directory',
           'get_os_version']
  
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

  file_contents = """\
#!/bin/sh
#---------- This file automatically generated by osg-configure
#---------- This is periodically overwritten.  DO NOT HAND EDIT
#---------- Instead, write any environment variable customizations into
#---------- the config.ini [Local Settings] section, as documented here:
#---------- https://twiki.grid.iu.edu/bin/view/ReleaseDocumentation/ConfigurationFileLocalSettings
#---  variables -----
%s
#--- export variables -----
%s
""" % (variable_string, export_string)

  atomic_write(filename, file_contents, mode=0644)
  return True

def get_set_membership(test_set, reference_set, defaults=None):
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
    return socket.getfqdn()
  # pylint: disable-msg=W0703
  except Exception:
    return None


def blank(value):
  """Check the value to check to see if it is 'UNAVAILABLE' or blank, return True 
  if that's the case
  """
  if value is None:
    return True

  temp_val = str(value)

  return (temp_val.upper().startswith('UNAVAILABLE') or
          temp_val.upper() == 'DEFAULT' or
          temp_val == "" or
          temp_val is None)


def get_vos(user_vo_file):
  """
  Returns a list of valid VO names.
  """

  if (user_vo_file is None or 
      not os.path.isfile(user_vo_file)):
    user_vo_file = '/var/lib/osg/user-vo-map'
  if not os.path.isfile(user_vo_file):
    return []
  file_buffer = open(user_vo_file, 'r')
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
  if service_name is None or service_name == "":
    return False
  process = subprocess.Popen(['/sbin/service', '--list', service_name], 
                             stdout=subprocess.PIPE)
  output = process.communicate()[0]
  if process.returncode != 0:
    return False  

  match = re.search(service_name + r'\s*\|.*\|\s*([a-z ]*)$', output)
  if match:
    # The regex above captures trailing whitespace, so remove it
    # before we make the comparison. -Scot Kronenfeld 2010-10-08
    if match.group(1).strip() == 'enable':
      return True
    else:
      return False
  else:
    return False 
  
def create_map_file(using_gums=False):
  """
  Check and create a mapfile if needed
  """

  map_file = '/var/lib/osg/osg-user-vo-map'
  result = True
  try:
    if validation.valid_user_vo_file(map_file):
      return result
    if using_gums:
      gums_script = '/usr/bin/gums-host-cron'
    else:
      gums_script = '/usr/bin/edg-mkgridmap'
      
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
    crl_files = glob.glob('/etc/grid-security/certificates/*.r0')
    if len(crl_files) > 0:
      sys.stdout.write("CRLs exist, skipping fetch-crl invocation\n")
      sys.stdout.flush()
      return True
    
    crl_path = '/usr/sbin'
    if rpm_installed('fetch-crl'):
      crl_path = os.path.join(crl_path, 'fetch-crl')
    elif rpm_installed('fetch-crl3'):
      crl_path = os.path.join(crl_path, 'fetch-crl3')
    if not validation.valid_file(crl_path):
      sys.stdout.write("Can't find fetch-crl script, skipping fetch-crl invocation\n")
      sys.stdout.flush()
      return True

    sys.stdout.write("Running %s, this process may take " % crl_path +
                     "some time to fetch all the crl updates\n")
    sys.stdout.flush()

    # Some CRLs are often problematic; it's better to ignore some errors than to halt configuration. (SOFTWARE-1428)
    error_message_whitelist = [ # whitelist partially taken from osg-test
      'CRL has lastUpdate time in the future',
      'CRL has nextUpdate time in the past',
      'CRL verification failed for',
      'Download error',
      'CRL retrieval for',
      r'^\s*$',
    ]
    fetch_crl_process = subprocess.Popen([crl_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    outerr = fetch_crl_process.communicate()[0]
    if fetch_crl_process.returncode != 0:
      sys.stdout.write("fetch-crl script had some errors:\n" + outerr + "\n")
      sys.stdout.flush()
      for line in outerr.rstrip("\n").split("\n"):
        found = False
        for msg in error_message_whitelist:
          if re.search(msg, line):
            found = True
            break
        if not found:
          return False
      sys.stdout.write("Ignoring errors and continuing\n")
      sys.stdout.flush()
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


def get_condor_location(default_location='/usr'):
  """
  Check environment variables to try to get condor location
  """

  if 'CONDOR_LOCATION' in os.environ:
    return os.path.normpath(os.environ['CONDOR_LOCATION'])  
  elif not blank(default_location):
    return default_location
  else:
    return ""


def get_condor_config(default_config='/etc/condor/condor_config'):
  """
  Check environment variables to try to get condor config
  """
  
  if 'CONDOR_CONFIG' in os.environ:
    return os.path.normpath(os.environ['CONDOR_CONFIG'])
  elif not blank(default_config):
    return os.path.normpath(default_config)
  else:
    return os.path.join(get_condor_location(), 'etc/condor_config')


def get_condor_config_val(variable, executable='condor_config_val'):
  """
  Use condor_config_val to return the expanded value of a variable.

  Arguments:
  variable - name of the variable whose value to return
  executable - the name of the executable to use (in case we want to poll condor_ce_config_val or
               condor_cron_config_val)

  Returns:
  The stripped output of condor_config_val, or None if condor_config_val reports an error.
  """
  try:
    process = subprocess.Popen([executable, '-expand', variable],
                               stdout=subprocess.PIPE)
    output = process.communicate()[0]
    if process.returncode != 0:
      return None
    return output.strip()
  except OSError:
    return None


def atomic_write(filename=None, contents=None, **kwargs):
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

  if filename is None or contents is None:
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
        # need to fsync data to make sure data is written on disk before renames
        # see ext4 documentation for more information
        os.fsync(config_fd)
      finally:
        os.close(config_fd)
    except:
      os.unlink(temp_name)
      raise 
    os.rename(temp_name, filename)
    os.chmod(filename, mode)
  except Exception:
    return False
  return True


def ce_installed():
  """
  Return True if one of the base osg-ce metapackages (osg-ce or osg-htcondor-ce) is installed
  """
  return any_rpms_installed('osg-ce', 'osg-htcondor-ce')


def gateway_installed():
  """
  Check to see if a job gateway (i.e. globus-gatekeeper or htcondor-ce) is installed
  """
  return any_rpms_installed('globus-gatekeeper', 'htcondor-ce')


def any_rpms_installed(*rpm_names):
  """
  Check if any of the rpms in the list are installed
  :param rpms: One or more RPM names
  :return: True if any of the listed RPMs are installed, False otherwise
  """
  return (True in (rpm_installed(rpm_name) for rpm_name in rpm_names))


def rpm_installed(rpm_name):
  """
  Check to see if given rpm is installed
  
  Arguments:
  rpm_name - a string with rpm name to check or a Iteratable with rpms that
             should be checked

  Returns:
  True if rpms are installed, False otherwise
  """
  trans_set = rpm.TransactionSet()
  if isinstance(rpm_name, types.StringType):
    return trans_set.dbMatch('name', rpm_name).count() in (1, 2)

  # check with iterable type
  try:
    for name in rpm_name:
      if trans_set.dbMatch('name', name).count() not in (1, 2):
        return False
    return True
  # pylint: disable-msg=W0703
  except Exception:
    return False


def get_test_config(config_file=''):
  """
  Try to figure out whether where the config files for unit tests are located,
  preferring the ones in the local directory
  
  Arguments:
  config_file - name of config file being checked, can be an empty string or 
    set to None
  
  Returns:
  the prefixed config file if config_file is non-empty, otherwise just the 
  prefix, returns None if no path exists
  """

  config_prefix = './configs'
  sys_prefix = '/usr/share/osg-configure/tests/configs'

  if config_file == '' or config_file is None:
    return None 

  test_location = os.path.join(config_prefix, config_file)
  if os.path.exists(test_location):
    return os.path.abspath(test_location)
  test_location = os.path.join(sys_prefix, config_file)
  if os.path.exists(test_location):
    return os.path.abspath(test_location)
  return None


def make_directory(dir_name, perms=0755, uid=None, gid=None):
  """
  Create a directory with specified permissions and uid/gid.  Will use the 
  current user's uid and gid if not specified.
  
  returns True is successful
  """
  
  if uid is None:
    uid = os.getuid()
  if gid is None:
    gid = os.getgid()
  try:
    os.makedirs(dir_name, perms)
    os.chown(dir_name, uid, gid)
    return True
  except IOError:
    return False


def get_os_version():
  """
  Get and return OS major version
  """
  version = platform.dist()[1]
  version_list = [int(x) for x in version.split('.')]
  return version_list

