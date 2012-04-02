#!/usr/bin/env python

import os, imp, sys, unittest, ConfigParser, types

# setup system library path
pathname = os.path.realpath('../')
sys.path.insert(0, pathname)

from osg_configure.modules import exceptions
from osg_configure.modules import exceptions
from osg_configure.modules import utilities

pathname = os.path.join('../scripts', 'osg-configure')

try:
    has_configure_osg = False
    fp = open(pathname, 'r')
    configure_osg = imp.load_module('test_module', fp, pathname, ('', '', 1))
    has_configure_osg = True
except:
    raise

class TestUtilities(unittest.TestCase):

    def test_write_attribute_file(self):
      """
      Check to make sure that write_attribute_file writes out files properly
      """
      attribute_file = os.path.abspath("./test_files/temp_attributes.conf")
      attribute_standard = os.path.abspath("./test_files/attributes_output.conf")
      try:
        attributes = {'Foo' : 123,
                      'test_attr' : 'abc-234#$',
                      'my-Attribute' : 'test_attribute'}
        utilities.write_attribute_file(attribute_file, attributes)
        self.failUnlessEqual(open(attribute_file).read(), 
                             open(attribute_standard).read(), 
                             'Attribute files are not equal')
        if os.path.exists(attribute_file):
          os.unlink(attribute_file)
      except Exception, ex:
        self.fail('Got exception while testing wite_attribute_file' \
                  "functionality:\n%s" % ex)
        if os.path.exists(attribute_file):
          os.unlink(attribute_file)
      
    def test_get_set_membership(self):
      """
      Test get_set_membership functionality
      """
      
      test_set1 = [1, 2, 3, 4, 5, 6, 7]
      reference_set1 = [1, 2, 3, 4, 5]
      default_set1 = [5, 6, 7]
      
      self.failUnlessEqual(utilities.get_set_membership(test_set1, 
                                                        reference_set1), 
                            [6, 7],
                            'Did not get [6, 7] as missing set members')

      self.failUnlessEqual(utilities.get_set_membership(test_set1, 
                                                        reference_set1,
                                                        default_set1), 
                            [],
                            'Did not get [] as missing set members')

      self.failUnlessEqual(utilities.get_set_membership(reference_set1, 
                                                        reference_set1), 
                            [],
                            'Did not get [] as missing set members')

      test_set2 = ['a', 'b', 'c', 'd', 'e']
      reference_set2 = ['a', 'b', 'c']
      default_set2 = ['d', 'e']
      self.failUnlessEqual(utilities.get_set_membership(test_set2, 
                                                        reference_set2), 
                            ['d', 'e'],
                            'Did not get [d, e] as missing set members')

      self.failUnlessEqual(utilities.get_set_membership(test_set2, 
                                                        reference_set2,
                                                        default_set2), 
                            [],
                            'Did not get [] as missing set members')

      self.failUnlessEqual(utilities.get_set_membership(reference_set2, 
                                                        reference_set2), 
                            [],
                            'Did not get [] as missing set members')

    def test_blank(self):
      """
      Test functionality of blank function
      """
      
      self.failIf(utilities.blank(1), 
                  'blank indicated 1 was a blank value')
      self.failIf(utilities.blank('a'), 
                  'blank indicated a was a blank value')
      self.failUnless(utilities.blank('unavailable'), 
                      'blank did not indicate unavailable was a blank value')
      self.failUnless(utilities.blank(None), 
                      'blank did not indicate None was a blank value')
      self.failUnless(utilities.blank('unavAilablE'), 
                      'blank did not indicate unavAilablE was a blank value')

    def test_get_vos(self):
      """
      Test get_vos function
      """  
      
      vo_file = os.path.abspath('./test_files/sample-vos.txt')
      self.failUnlessEqual(utilities.get_vos(vo_file), 
                           ['osg', 'LIGO', 'cdf'], 
                           "Correct vos not found")
      
    def test_rpm_install(self):
      """
      Test rpm_installed function
      """
      rpm_name = 'foo'
      self.assertFalse(utilities.rpm_installed(rpm_name),
                       'foo is not installed, but rpm_installed returned True')
      rpm_name = 'filesystem'
      self.assert_(utilities.rpm_install(rpm_name),
                   'filesystem is installed, but rpm_installed returned False')

      rpm_names = ['filesystem', 'foo']
      self.assertFalse(utilities.rpm_installed(rpm_names),
                       'foo is not installed, but rpm_installed returned True')
      rpm_names = ['filesystem', 'glibc']
      self.assert_(utilities.rpm_installed(rpm_names),
                  'filesystem and glibc are installed, but rpm_installed returned False')
      
if __name__ == '__main__':
    unittest.main()

