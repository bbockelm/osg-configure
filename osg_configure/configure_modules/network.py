#!/usr/bin/python

""" Module to handle attributes related to the site location and details """

import os, logging, re

from osg_configure.modules import exceptions
from osg_configure.modules import utilities
from osg_configure.modules import configfile
from osg_configure.modules import validation
from osg_configure.modules.configurationbase import BaseConfiguration

__all__ = ['NetworkConfiguration']


class NetworkConfiguration(BaseConfiguration):
  """Class to handle attributes related to network configuration"""

  def __init__(self, *args, **kwargs):
    # pylint: disable-msg=W0142
    super(NetworkConfiguration, self).__init__(*args, **kwargs)
    self.log('NetworkConfiguration.configure started')    
    self.options = {'source_range' : 
                      configfile.Option(name = 'source_range',
                                        default_value = '',
                                        required = configfile.Option.OPTIONAL),
                    'source_state_file' : 
                      configfile.Option(name = 'source_state_file',
                                        default_value = '',
                                        required = configfile.Option.OPTIONAL),
                    'port_range' : 
                      configfile.Option(name = 'port_range',
                                        default_value = '',
                                        required = configfile.Option.OPTIONAL),
                    'port_state_file' : 
                      configfile.Option(name = 'port_state_file',
                                        default_value = '',
                                        required = configfile.Option.OPTIONAL)}
    self.config_section = 'Network'
    self.log('NetworkConfiguration.configure completed')    
      
  def parseConfiguration(self, configuration):
    """Try to get configuration information from ConfigParser or SafeConfigParser object given
    by configuration and write recognized settings to attributes dict
    """
    self.log('NetworkConfiguration.parseConfiguration started')

    self.checkConfig(configuration)


    if not configuration.has_section(self.config_section):
      self.log('Network section not found in config file')
      self.log('NetworkConfiguration.parseConfiguration completed')
      self.enabled = False
      return
    
    self.enabled = True
    for option in self.options.values():
      self.log("Getting value for %s" % option.name)
      configfile.get_option(configuration,
                            self.config_section, 
                            option)
      self.log("Got %s" % option.value)
        
    # check and warn if unknown options found 
    temp = utilities.get_set_membership(configuration.options(self.config_section),
                                        self.options.keys(),
                                        configuration.defaults().keys())
    for option in temp:
      self.log("Found unknown option",
               option = option, 
               section = self.config_section,
               level = logging.WARNING)
    self.log('NetworkConfiguration.parseConfiguration completed')    
     

# pylint: disable-msg=W0613
  def checkAttributes(self, attributes):
    """Check attributes currently stored and make sure that they are consistent"""
    self.log('NetworkConfiguration.checkAttributes started')
    attributes_ok = True
    
    for name in ['source_state_file', 'port_state_file']:
      if utilities.blank(self.options[name].value):
        continue
      
      if not validation.valid_location(self.options[name].value):
        self.log("Invalid location: %s" % self.options[name].value,
                 option = name,
                 section = self.config_section,
                 level = logging.ERROR)
        attributes_ok = False

    for name in ['source_range', 'port_range']:
      if utilities.blank(self.options[name].value):
        continue

      matches = re.match('(\d+),(\d+)', self.options[name].value)
      if matches is None:
        self.log("Invalid range specification, expected low_port,high_port, " +
                 "got %s" % self.options[name].value,
                 option = name,
                 section = self.config_section,
                 level = logging.ERROR)
        attributes_ok = False
      
    if (not utilities.blank(self.options['source_state_file'].value) and
        utilities.blank(self.options['source_range'].value)):
        self.log("If you specify a source_state_file, " +
                 "source_range must be given",
                 option = 'source_state_file',
                 section = self.config_section,
                 level = logging.ERROR)
        attributes_ok = False
        
    if (not utilities.blank(self.options['port_state_file'].value) and
        utilities.blank(self.options['port_range'].value)):
        self.log("If you specify a port_state_file, " +
                 "port_range must be given",
                 option = 'port_state_file',
                 section = self.config_section,
                 level = logging.ERROR)
        attributes_ok = False

    self.log('NetworkConfiguration.checkAttributes completed')        
    return attributes_ok 

  def configure(self, attributes):
    """
    Setup basic osg/vdt services
    """

    self.log("NetworkConfiguration.configure started")
    status = True

    header = "# This file is automatically generated by osg-configure"
    header += "# based on the settings in the [Network] section, please"
    header += "# make changes there instead of manually editing this file"
    source_settings_sh = ''
    source_settings_csh = ''
    if not utilities.blank(self.options['source_range'].value):
      source_settings_sh = "export GLOBUS_TCP_SOURCE_RANGE_STATE_FILE=%s\n" % \
                           self.options['source_state_file'].value 
      source_settings_sh += "export GLOBUS_TCP_SOURCE_RANGE=%s\n" % \
                            self.options['source_state_file'].value 
      source_settings_csh = "setenv GLOBUS_TCP_SOURCE_RANGE_STATE_FILE=%s\n" % \
                            self.options['source_state_file'].value 
      source_settings_csh += "setenv GLOBUS_TCP_SOURCE_RANGE=%s\n" % \
                             self.options['source_state_file'].value 
    if not utilities.blank(self.options['port_range'].value):
      port_settings_sh = "export GLOBUS_TCP_PORT_RANGE_STATE_FILE=%s\n" % \
                           self.options['port_state_file'].value 
      port_settings_sh += "export GLOBUS_TCP_PORT_RANGE=%s\n" % \
                            self.options['port_state_file'].value 
      port_settings_csh = "setenv GLOBUS_TCP_PORT_RANGE_STATE_FILE=%s\n" % \
                            self.options['port_state_file'].value 
      port_settings_csh += "setenv GLOBUS_TCP_PORT_RANGE=%s\n" % \
                             self.options['port_state_file'].value 
    buffer = "#!/bin/sh\n" + source_settings_sh + port_settings_sh
    filename = os.path.join('/', 'var', 'lib', 'osg' , 'globus-firewall')
    if not utilities.atomic_write(filename, buffer):
      self.log("Error writing to %s" % filename,
               level = logging.ERROR)
      status = False
    filename = os.path.join('/', 'etc', 'profile.d', 'osg.sh')
    if not utilities.atomic_write(filename, buffer):
      self.log("Error writing to %s" % filename,
               level = logging.ERROR)
      status = False
    buffer = "#!/bin/csh\n" + source_settings_csh + port_settings_csh
    filename = os.path.join('/', 'etc', 'profile.d', 'osg.csh')
    if not utilities.atomic_write(filename, buffer):
      self.log("Error writing to %s" % filename,
               level = logging.ERROR)
      status = False
        
    self.log("NetworkConfiguration.configure completed")    
    return status

  def moduleName(self):
    """Return a string with the name of the module"""
    return "NetworkConfiguration"
  
  def separatelyConfigurable(self):
    """Return a boolean that indicates whether this module can be configured separately"""
    return True
  
  def parseSections(self):
    """Returns the sections from the configuration file that this module handles"""
    return [self.config_section]

    
