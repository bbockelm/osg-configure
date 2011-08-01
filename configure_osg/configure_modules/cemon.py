#!/usr/bin/python


"""This module provides a class to handle attributes and configuration
 for CEMON subscriptions"""

import os, ConfigParser, re, urlparse

from configure_osg.modules import exceptions
from configure_osg.modules import utilities
from configure_osg.modules.configurationbase import BaseConfiguration

__all__ = ['CemonConfiguration']


class CemonConfiguration(BaseConfiguration):
  """
  Class to handle attributes and configuration related to 
  miscellaneous services
  """
  
  CEMON_CONFIG_FILE = "/etc/glite/cemonitor-config.xml"
  def __init__(self, *args, **kwargs):
    # pylint: disable-msg=W0142
    super(CemonConfiguration, self).__init__(*args, **kwargs)
    self.logger.debug("CemonConfiguration.__init__ started")
    # file location for xml file with cemon subscriptions
    self.__cemon_configuration_file = os.path.join(self.CEMON_CONFIG_FILE)
    self.config_section = 'Cemon'
    self.__mappings = {'ress_servers' : 'ress_servers',
                       'bdii_servers' : 'bdii_servers'}
    self.__defaults = {}
    self.__itb_defaults = {'ress_servers' : 'https://osg-ress-4.fnal.gov:8443/ig/' \
                                            'services/CEInfoCollector[OLD_CLASSAD]',
                           'bdii_servers' : 'http://is-itb1.grid.iu.edu:14001[RAW],' \
                                            'http://is-itb2.grid.iu.edu:14001[RAW]'}
    self.__production_defaults = {'ress_servers' :
                                    'https://osg-ress-1.fnal.gov:8443/ig/' \
                                    'services/CEInfoCollector[OLD_CLASSAD]',
                                  'bdii_servers' :
                                    'http://is1.grid.iu.edu:14001[RAW],' \
                                    'http://is2.grid.iu.edu:14001[RAW]'}
    self.bdii_servers = {}
    self.ress_servers = {}
    self.logger.debug("CemonConfiguration.__init__ completed")

  def parseConfiguration(self, configuration):
    """
    Try to get configuration information from ConfigParser or SafeConfigParser object given
    by configuration and write recognized settings to attributes dict    
    """
    
    self.logger.debug('CemonConfiguration.parseConfiguration started')

    self.checkConfig(configuration)

    if (not configuration.has_section(self.config_section) and 
        utilities.ce_config(configuration)):
      self.logger.debug('Section missing and on a ce, autoconfiguring')
      self.__auto_configure(configuration)
      self.logger.debug('CemonConfiguration.parseConfiguration completed')
      return True        
    elif not configuration.has_section(self.config_section):  
      self.enabled = False
      self.logger.debug("%s section not in config file" % self.config_section)
      self.logger.debug('Cemon.parseConfiguration completed')
      return
    
    if not self.setStatus(configuration):
      self.logger.debug('Cemon.parseConfiguration completed')
      return True
       
    if utilities.ce_config(configuration):
      if configuration.has_option('Site Information', 'group'):
        group = configuration.get('Site Information', 'group')
      if group == 'OSG':
        self.__defaults = self.__production_defaults
      elif group == 'OSG-ITB':
        self.__defaults = self.__itb_defaults
        
    for setting in self.__mappings:
      self.logger.debug("Getting value for %s" % setting)
      temp = utilities.get_option(configuration, 
                                  self.config_section, 
                                  setting,
                                  defaults = self.__defaults)
      self.attributes[setting] = temp
      self.logger.debug("Got %s" % temp)
    
    self.ress_servers = self.__parse_servers(self.attributes['ress_servers'])  
    self.bdii_servers = self.__parse_servers(self.attributes['bdii_servers'])  
      
# pylint: disable-msg=W0613
  def configure(self, attributes):
    """Configure installation using attributes"""
    self.logger.debug("CemonConfiguration.configure started")

    if self.ignored:
      self.logger.warning("%s configuration ignored" % self.config_section)
      return True

    # disable configuration for now
    self.logger.debug("Not enabled")
    self.logger.debug("CemonConfiguration.configure completed")
    return True
        
    if not self.enabled:
      self.logger.debug("Not enabled")
      self.logger.debug("CemonConfiguration.configure completed")
      return True
    
    self.logger.debug("Making BDII subscriptions")
    for subscription in self.bdii_servers:
      dialect = self.bdii_servers[subscription]
      self.logger.debug("Subscribing to %s using %s dialect" % (subscription,
                                                                dialect))
      self.configureSubscriptions(subscription = subscription, 
                                  dialect = dialect)
        

    self.logger.debug("Making ReSS subscriptions")
    for subscription in self.ress_servers:
      dialect = self.ress_servers[subscription]
      self.logger.debug("Subscribing to %s using %s dialect" % (subscription,
                                                                dialect))
      self.configureSubscriptions(subscription = subscription, dialect = dialect)


    if not utilities.enable_service('tomcat-55'):
      self.logger.error("Error while enabling tomcat")
      raise exceptions.ConfigureError("Error configuring cemon")
    self.logger.debug("Enabling apache service")
    if not utilities.enable_service('apache'):
      self.logger.error("Error while enabling apache")
      raise exceptions.ConfigureError("Error enabling apache") 

    self.logger.debug("CemonConfiguration.configure completed")
    return True

  def checkAttributes(self, attributes):
    """Check configuration and make sure things are setup correctly"""
    self.logger.debug("CemonConfiguration.checkAttributes started")
    
    if not self.enabled:
      self.logger.debug("Not enabled")
      self.logger.debug("CemonConfiguration.checkAttributes completed")
      return True

    if self.ignored:
      self.logger.debug('Ignored, returning True')
      self.logger.debug("CemonConfiguration.checkAttributes completed")
      return attributes_ok
    
    valid = True
    self.logger.debug("Checking BDII subscriptions")
    for subscription in self.bdii_servers:
      valid &= self.__checkSubscription(subscription, 
                                        self.bdii_servers[subscription])
      
    self.logger.debug("Checking ReSS subscriptions")
    for subscription in self.ress_servers:
      valid &= self.__checkSubscription(subscription, 
                                        self.ress_servers[subscription])

    self.logger.debug("CemonConfiguration.checkAttributes completed")
    return valid

  def moduleName(self):
    """Return a string with the name of the module"""
    return "CEMon"
  
  def separatelyConfigurable(self):
    """Return a boolean that indicates whether this module can be 
    configured separately"""
    return False
  
  def configureSubscriptions(self, subscription = None, dialect = "RAW"):
    """Check to see if subscriptions is already present and if not
    make them"""

    self.logger.debug("CemonConfiguration.configureSubscriptions started")
    if subscription is None:
      return 
    
    # last two arguments get replaced with the subscription and dialect 
    arguments = ['--server', 'y', '--topic=OSG_CE', ' ', ' ']
    
    # check to see if subscriptions to production bdii or cemon collectors
    # present
    found_subscriptions = {}
    for element in utilities.get_elements('subscription', 
                                          self.__cemon_configuration_file):
      try:
        found_subscriptions[element.getAttribute('monitorConsumerURL')] = True
      # pylint: disable-msg=W0703
      except Exception, ex:
        self.logger.debug("Exception checking element, %s" % ex)

    arguments[-1] = "--dialect=%s" % dialect
    if subscription not in found_subscriptions.keys():
      arguments[-2] = "--consumer=%s" % subscription
      self.logger.info("Running configure_cemon with: %s" % (" ".join(arguments)))
      if not utilities.configure_service('configure_cemon', arguments):
        self.logger.error("Error while subscribing to server")
        raise exceptions.ConfigureError("Error configuring cemon")
   

    self.logger.debug("CemonConfiguration.configureSubscriptions completed")

  def __checkSubscription(self, subscription, dialect):
    """
    Check a subscription and dialect to make sure it's valid, return True if 
    that's the case, otherwise false. 
    
    subscription must be a uri and dialect must be CLASSAD, RAW, or OLD_CLASSAD
    """

    valid = True
    # check for valid uri
    result = urlparse.urlsplit(subscription)
    if result[1] == '':
      self.logger.error("Subscription must be a uri, "\
                        "got %s" % subscription)
      valid = False
    
    # check to see if host resolves
    server = result[1]
    if ':' in server:
      server = server.split(':')[0]
    if not utilities.valid_domain(server, True):
      self.logger.error("Host in subscription does " \
                        "not resolve: %s" % server)
      valid = False
    
    # check to make sure dialect is correct
    if dialect not in ('CLASSAD', 'RAW', 'OLD_CLASSAD'):
      self.logger.error("Dialect for subscription %s is " \
                        "not valid: %s" % (server, dialect))
      valid = False
    return valid

  def __parse_servers(self, servers):
    """
    Take a list of servers and parse it into a list of 
    (server, subscription_type) tuples
    """
    server_list = {}
    if servers.lower() == 'ignore':
      # if the server list is set to ignore, then don't use any servers
      # this allows cemon to be send ress information but not bdii or vice versa
      return server_list
    
    server_regex = re.compile('(.*)\[(.*)\]')
    for entry in servers.split(','):
      match = server_regex.match(entry)
      if match is None:
        raise exceptions.SettingError('Invalid subscription: %s' % entry)
      server_list[match.group(1).strip()] = match.group(2)
    return server_list
    
  def __auto_configure(self, configuration):
    """
    Method to configure cemon without any cemon section on a CE
    """
    
    self.enabled = True
    if configuration.has_option('Site Information', 'group'):
      group = configuration.get('Site Information', 'group')
    else:
      self.logger.error('No group defined in Site Information, ' \
                        'this is required on a CE')
      raise exceptions.SettingError('In Site Information, ' \
                                    'group needs to be set')
    if group == 'OSG':
      ress_servers = self.__production_defaults['ress_servers']
      bdii_servers = self.__production_defaults['bdii_servers']
    elif group == 'OSG-ITB':
      ress_servers = self.__itb_defaults['ress_servers']
      bdii_servers = self.__itb_defaults['bdii_servers']
    
    self.attributes['ress_servers'] = ress_servers
    self.attributes['bdii_servers'] = bdii_servers 
    self.ress_servers = self.__parse_servers(ress_servers)
    self.bdii_servers = self.__parse_servers(bdii_servers)