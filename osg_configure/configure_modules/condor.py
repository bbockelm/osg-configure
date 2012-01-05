#!/usr/bin/python

""" Module to handle attributes and configuration related to the condor 
jobmanager configuration """

import os, ConfigParser, types, logging, re

from osg_configure.modules import utilities
from osg_configure.modules import validation
from osg_configure.modules import configfile
from osg_configure.modules import exceptions
from osg_configure.modules.jobmanagerbase import JobManagerConfiguration

__all__ = ['CondorConfiguration']



class CondorConfiguration(JobManagerConfiguration):
  """Class to handle attributes related to condor job manager configuration"""
  
  CONDOR_CONFIG_FILE = '/etc/grid-services/available/jobmanager-condor'
  GRAM_CONFIG_FILE = '/etc/globus/globus-condor.conf'
  def __init__(self, *args, **kwargs):
    # pylint: disable-msg=W0142
    super(CondorConfiguration, self).__init__(*args, **kwargs)
    self.log('CondorConfiguration.__init__ started')    
    self.config_section = "Condor"
    self.options = {'condor_location' : 
                      configfile.Option(name = 'condor_location',
                                        default_value = utilities.get_condor_location(),
                                        mapping = 'OSG_CONDOR_LOCATION'),
                    'condor_config' : 
                      configfile.Option(name = 'condor_config',
                                        default_value = utilities.get_condor_config(),
                                        mapping = 'OSG_CONDOR_CONFIG'),
                    'job_contact' : 
                      configfile.Option(name = 'job_contact',
                                        mapping = 'OSG_JOB_CONTACT'),
                    'util_contact' : 
                      configfile.Option(name = 'util_contact',
                                        mapping = 'OSG_UTIL_CONTACT'),
                    'seg_enabled' : 
                      configfile.Option(name = 'seg_enabled',
                                        required = configfile.Option.OPTIONAL,
                                        type = bool,
                                        default_value = False),
                    'accept_limited' : 
                      configfile.Option(name = 'accept_limited',
                                        required = configfile.Option.OPTIONAL,
                                        type = bool,
                                        default_value = False)}
    self.__set_default = True
    self.log('CondorConfiguration.__init__ completed')    
      
  def parseConfiguration(self, configuration):
    """
    Try to get configuration information from ConfigParser or SafeConfigParser object given
    by configuration and write recognized settings to attributes dict
    """
    self.log('CondorConfiguration.parseConfiguration started')

    self.checkConfig(configuration)
      
    if not configuration.has_section(self.config_section):
      self.enabled = False
      self.log("%s section not in config file" % self.config_section)
      self.log('CondorConfiguration.parseConfiguration completed')
      return

    if not self.setStatus(configuration):
      self.log('CondorConfiguration.parseConfiguration completed')
      return True
           
    for option in self.options.values():
      self.log("Getting value for %s" % option.name)
      configfile.get_option(configuration,
                            self.config_section, 
                            option)
      self.log("Got %s" % option.value)

    # set OSG_JOB_MANAGER and OSG_JOB_MANAGER_HOME
    self.options['job_manager'] = configfile.Option(name = 'job_manager',
                                                    value = 'Condor',
                                                    mapping = 'OSG_JOB_MANAGER')
    self.options['home'] = configfile.Option(name = 'job_manager_home',
                                             value = self.options['condor_location'].value,
                                             mapping = 'OSG_JOB_MANAGER_HOME')
      
    # check and warn if unknown options found    
    temp = utilities.get_set_membership(configuration.options(self.config_section),
                                        self.options.keys(),
                                        configuration.defaults().keys())
    for option in temp:
      if option == 'enabled':
        continue
      self.log("Found unknown option",
               option = option,
               section = self.config_section,
               level = loggng.WARNING) 
      
    if (configuration.has_section('Managed Fork') and
        configuration.has_option('Managed Fork', 'enabled') and
        configuration.getboolean('Managed Fork', 'enabled')):
      self.__set_default = False

    self.log('CondorConfiguration.parseConfiguration completed')        

# pylint: disable-msg=W0613
  def checkAttributes(self, attributes):
    """Check attributes currently stored and make sure that they are consistent"""
    self.log('CondorConfiguration.checkAttributes started')

    if not self.enabled:
      self.log('CondorConfiguration.checkAttributes completed returning True')
      return True
    
    if self.ignored:
      self.log('CondorConfiguration.checkAttributes completed returning True')
      return True

    attributes_ok = True

    # make sure locations exist
    self.log('checking condor_location')
    if not validation.valid_location(self.options['condor_location'].value):
      attributes_ok = False
      self.log("Non-existent location given: %s" % 
                          (self.options['condor_location'].value),
                option = 'condor_location',
                section = self.config_section,
                level = logging.ERROR)

    self.log('checking condor_config')
    if not validation.valid_file(self.options['condor_config'].value):
      attributes_ok = False
      self.log("Non-existent location given: %s" % 
                          (self.options['condor_config'].value),
                option = 'condor_config',
                section = self.config_section,
                level = logging.ERROR)

    if not self.validContact(self.options['job_contact'].value, 
                             'condor'):
      attributes_ok = False
      self.log("Invalid job contact: %s" % 
                         (self.options['job_contact'].value),
               option = 'job_contact',
               section = self.config_section,
               level = logging.ERROR)
      
    if not self.validContact(self.options['util_contact'].value, 
                             'condor'):
      attributes_ok = False
      self.log("Invalid util contact: %s" % 
                        (self.options['util_contact'].value),
               option = 'util_contact',
               section = self.config_section,
               level = logging.ERROR)


    self.log('CondorConfiguration.checkAttributes completed returning %s' \
                       % attributes_ok)
    return attributes_ok 

  def configure(self, attributes):
    """Configure installation using attributes"""
    self.log('CondorConfiguration.configure started')

    if self.ignored:
      self.log("%s configuration ignored" % self.config_section, 
               level = logging.WARNING)
      self.log('CondorConfiguration.configure completed')
      return True

    if not self.enabled:
      self.log('condor not enabled')
      self.log('CondorConfiguration.configure completed')
      return True
            
    # The accept_limited argument was added for Steve Timm.  We are not adding
    # it to the default config.ini template because we do not think it is
    # useful to a wider audience.
    # See VDT RT ticket 7757 for more information.
    if self.options['accept_limited'].value:
      if not self.enable_accept_limited(CondorConfiguration.CONDOR_CONFIG_FILE):
        self.log('Error writing to ' + CondorConfiguration.CONDOR_CONFIG_FILE,
                 level = logging.ERROR)
        self.log('CondorConfiguration.configure completed')
        return False
    else:
      if not self.disable_accept_limited(CondorConfiguration.CONDOR_CONFIG_FILE):
        self.log('Error writing to ' + CondorConfiguration.GRAM_CONFIG_FILE,
                 level = logging.ERROR)
        self.log('CondorConfiguration.configure completed')
        return False

    if not self.setupGramConfig():
      self.log('Error writing to ' + CondorConfiguration.GRAM_CONFIG_FILE,
               level = logging.ERROR)
      return False
      
    if self.__set_default:
        self.log('Configuring gatekeeper to use regular fork service')
        self.set_default_jobmanager('fork')
      
    self.log('CondorConfiguration.configure completed')
    return True    
    
  def moduleName(self):
    """Return a string with the name of the module"""
    return "Condor"
  
  def separatelyConfigurable(self):
    """Return a boolean that indicates whether this module can be configured separately"""
    return True

  def parseSections(self):
    """Returns the sections from the configuration file that this module handles"""
    return [self.config_section]  
  
  def setupGramConfig(self):
    """
    Populate the gram config file with correct values
    
    Returns True if successful, False otherwise
    """    
    buffer = open(PBSConfiguration.GRAM_CONFIG_FILE).read()
    bin_location = os.path.join([self.options['condor_location'].value,
                                 'bin',
                                 'condor_submit'])
    if validation.valid_file(bin_location):
      (buffer, count) = re.subn('^condor_submit=.*$', "condor_submit=\"%s\"" % bin_location, 1)
      if count == 0:
        buffer = "condor_submit=\"%s\"\n" % bin_location + buffer
    bin_location = os.path.join([self.options['condor_location'].value,
                                 'bin',
                                 'condor_rm'])
    if validation.valid_file(bin_location):
      (buffer, count) = re.subn('^condor_rm=.*$', "condor_rm=\"%s\"" % bin_location, 1)
      if count == 0:
        buffer = "condor_rm=\"%s\"\n" % bin_location + buffer
    if not utilities.blank(self.options['condor_config'].value):
      (buffer, count) = re.subn('^condor_config=.*$', "condor_config=\"%s\"" % bin_location, 1)
      if count == 0:
        buffer = "condor_config=\"%s\"\n" % self.options['condor_config'].value
        
    
    if not utilities.atomic_write(CondorConfiguration.GRAM_CONFIG_FILE, buffer):
      return False
    
    return True

