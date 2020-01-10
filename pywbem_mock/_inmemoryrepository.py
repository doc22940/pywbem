#
# (C) Copyright 2020 InovaDevelopment.comn
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Karl  Schopmeyer <inovadevelopment.com>
#

"""
Mock WBEMConnection to allow pywbem users to test the pywbem client without
requiring a running WBEM server. This package mocks the WBEMConnection
methods that communicate with WBEMServers and mantain a fake server
repository that is the source and destination for information to
be used by the methods mocked.

For the module-level documentation, see mocksupport.rst.
"""

from __future__ import absolute_import, print_function

from pywbem import CIMError, BaseRepositoryConnection, \
    CIM_ERR_INVALID_NAMESPACE, CIM_ERR_FAILED, CIM_ERR_INVALID_PARAMETER, \
    CIM_ERR_NOT_FOUND, CIM_ERR_ALREADY_EXISTS, \
    CIMInstanceName, CIM_ERR_NAMESPACE_NOT_EMPTY

from pywbem._nocasedict import NocaseDict

from pywbem._utils import _format
from ._resolvermixin import ResolverMixin

__all__ = ['InMemoryRepository']


class InMemoryRepository(BaseRepositoryConnection, ResolverMixin):
    """
    Create an adaption of the MOF compiler MOFWBEMConnection class so that to
    directly use the attributes that represent the repository and implement a
    modified CreateClass that resolves the new class. This directs the compiler
    output directly  to the dictionaries for qualifiers, and instances in the
    FakedWBEMConnection object and replaces the CreateClass with a local method
    that allows resolving the created class before it is inserted into the
    repository.

    This class is private to pywbem_mock
    """
    def __init__(self, conn):
        """
        Parameters:

          conn (BaseRepositoryConnection):
            The underlying repository connection.

            `None` means that there is no underlying repository and all
            operations performed through this object will fail.
        """

        self.conn = conn
        self.conn_id = conn.conn_id
        self.class_names = {}
        # The CIM classes in the mock repository.
        # This is a dictionary of dictionaries where the top level key is the
        # CIM namespace name and the keys for each sub-dictionary in a
        # namespace are class names, and the values in each sub-dictionary are
        # the CIM classes in that namespace, represented as CIMClass objects.
        # The dictionaries are NocaseDict since namespaces should be case
        # insensitive.
        self.classes = NocaseDict()

        # The CIM qualifier types in the mock repository.
        # Same format as for classes above, except that the values in each
        # sub-dictionary are CIMQualifierDeclaration objects.
        self.qualifiers = NocaseDict()

        # The CIM instances in the mock repository.
        # Because instances do not have a name, the format is slightly
        # different: This is a dictionary of lists where the top level key is
        # the CIM namespace name and the value is a list of CIM instances in
        # that namespace, represented as CIMInstance objects.
        # TODO: ks. FUTURE maybe we should really have a subdict per class but
        #  it is probably not important for initial release.
        self.instances = {}

        # Methods that will be executed. This is a dictionary of dictionaries
        # where the top level is the CIMNamespace, the next level is the
        # class in which the method will execute, and the third level defines
        # the method to be executed.  The value is the callback method to
        # be executed
        self.methods = NocaseDict()

        # The namespaces that may exist in the mock repository. This is a
        # dictionary where the key is the namespace name, and the value does
        # not matter (this approach is used to ensure namespace names are
        # treated case insensitively). This set of namespaces is used to
        # control into which namespaces of the mock repository classes,
        # qualifier types and instances may be added.
        self.namespaces = NocaseDict()
        self.add_namespace(conn.default_namespace)

        self.compile_ordered_classnames = []
        # TODO confirm.  We must always have a conn to make this work
        # Maybe not right in general since this is a server component.
        # if conn is None:
        #    # This attribute is used only to make get/set
        #    # of 'default_namespace' behave as it should, in the case
        #    # of conn=None.
        #    self.__default_namespace = conn

    ####################################################################
    #
    # Managing namespaces, add delete, validate
    #
    ####################################################################
    def _getns(self):
        """
        :term:`string`: Return the default repository namespace to be used.

        This method exists for compatibility. Use the :attr:`default_namespace`
        property instead.
        """
        if self.conn is not None:
            return self.conn.default_namespace
        return self.__default_namespace

    def _setns(self, value):
        """
        Set the default repository namespace to be used.

        This method exists for compatibility. Use the :attr:`default_namespace`
        property instead.
        """
        if self.conn is not None:
            self.conn.default_namespace = value
        else:
            self.__default_namespace = value

    getns = _getns  # for compatibility
    setns = _setns  # for compatibility

    default_namespace = property(
        _getns, _setns, None,
        """
        :term:`string`: The default repository namespace to be used.

        The default repository namespace is the default namespace of the
        underlying repository connection if there is such an underlying
        connection, or the default namespace of this object.

        Initially, the default namespace of this object is 'root/cimv2'.

        This property is settable. Setting it will cause the default namespace
        of the underlying repository connection to be updated if there is such
        an underlying connection, or the default namespace of this object.
        """
    )

    default_namespace = property(
        _getns, _setns, None,
        """
        :term:`string`: The default repository namespace to be used.

        The default repository namespace is the default namespace of the
        underlying repository connection if there is such an underlying
        connection, or the default namespace of this object.

        Initially, the default namespace of this object is 'root/cimv2'.

        This property is settable. Setting it will cause the default namespace
        of the underlying repository connection to be updated if there is such
        an underlying connection, or the default namespace of this object.
        """
    )

    def validate_namespace(self, namespace):
        """
        Validate whether a CIM namespace exists in the mock repository.

        Parameters:

          namespace (:term:`string`):
            The name of the CIM namespace in the mock repository. Must not be
            `None`.

        Returns: (:class:`py:bool`)
            Returns True if the namespace exists.
            or False if the namespace does not exist

        Raises:

            KeyError if the namespace is not a valid namespace in the
            repository
        """
        # Normalize the namespace name
        namespace = namespace.strip('/')

        return namespace in self.namespaces

    def add_namespace(self, namespace):
        """
        Add a CIM namespace to the mock repository.

        The namespace must not yet exist in the mock repository.

        Note that the default connection namespace is automatically added to
        the mock repository upon creation of this object.

        Parameters:

          namespace (:term:`string`):
            The name of the CIM namespace in the mock repository. Must not be
            `None`. Any leading and trailing slash characters are split off
            from the provided string.

        Raises:

          ValueError: Namespace argument must not be None
          KeyError: if the namespace already exists in the mock repository.
        """

        if namespace is None:
            raise ValueError("Namespace argument must not be None")

        # Normalize the namespace name by removing leading and trailing /
        namespace = namespace.strip('/')

        # Generate KeyError exception if namespace already exists
        if namespace in self.namespaces:
            raise KeyError()

        self.namespaces[namespace] = True

        # construct the namespace dictionaries for the cim object store
        self.classes[namespace] = NocaseDict()
        self.instances[namespace] = {}
        self.qualifiers[namespace] = NocaseDict()
        self.methods[namespace] = NocaseDict()

        return True

    def _remove_namespace(self, namespace):
        """
        Remove a CIM namespace from the mock repository.

        The namespace must exist in the mock repository and must be empty.

        The default connection namespace cannot be removed.

        Parameters:

          namespace (:term:`string`):
            The name of the CIM namespace in the mock repository. Must not be
            `None`. Any leading and trailing slash characters are split off
            from the provided string.

        Raises:

          ValueError: Namespace argument must not be None
          CIMError: CIM_ERR_NOT_FOUND if the namespace does not exist in
            the mock repository.
          CIMError: CIM_ERR_NAMESPACE_NOT_EMPTY if the namespace is not empty.
          CIMError: CIM_ERR_NAMESPACE_NOT_EMPTY if the default connection
            namespace was attempted to be deleted.
        """

        if namespace is None:
            raise ValueError("Namespace argument must not be None")

        # Normalize the namespace name by removing leading and trailing /
        namespace = namespace.strip('/')

        if namespace not in self.namespaces:
            raise CIMError(
                CIM_ERR_NOT_FOUND,
                _format("Namespace {0!A} does not exist in the mock "
                        "repository", namespace))

        if not self._class_repo_empty(namespace) or \
                not self._instance_repo_empty(namespace) or \
                not self._qualifier_repo_empty(namespace):
            raise CIMError(
                CIM_ERR_NAMESPACE_NOT_EMPTY,
                _format("Namespace {0!A} is not empty", namespace))

        if namespace == self.default_namespace:
            raise CIMError(
                CIM_ERR_NAMESPACE_NOT_EMPTY,
                _format("Connection default namespace {0!A} cannot be "
                        "deleted from mock repository", namespace))

        del self.namespaces[namespace]

    ###################################################################
    #
    # Low level CIM object test and get methods
    #
    ###################################################################

    def _class_repo_empty(self, namespace):
        """
        Returns a bool indicating whether the class repository for the
        specified CIM namespace within the mock repository is empty.

        The class repository is considered empty if it does not exist for
        the namespace, or if it exists and is empty.

        Parameters:

          namespace(:term:`string`): Namespace name. Must not be `None`.

        Returns:

          bool: Class repository is empty (or does not exist for the namespace)
        """
        return namespace not in self.classes \
            or not self.classes[namespace]

    def _instance_repo_empty(self, namespace):
        """
        Returns a bool indicating whether the instance repository for the
        specified CIM namespace within the mock repository is empty.

        The instance repository is considered empty if it does not exist for
        the namespace, or if it exists and is empty.

        Parameters:

          namespace(:term:`string`): Namespace name. Must not be `None`.

        Returns:

          bool: Instance repository is empty (or does not exist for the
            namespace)
        """
        return namespace not in self.instances \
            or not self.instances[namespace]

    def _qualifier_repo_empty(self, namespace):
        """
        Returns a bool indicating whether the qualifier repository for the
        specified CIM namespace within the mock repository is empty.

        The qualifier repository is considered empty if it does not exist for
        the namespace, or if it exists and is empty.

        Parameters:

          namespace(:term:`string`): Namespace name. Must not be `None`.

        Returns:

          bool: Qualifier repository is empty (or does not exist for the
            namespace)
        """
        return namespace not in self.qualifiers or \
            not self.qualifiers[namespace]

    def validate_repo(self, namespace, repo_name):
        """
        Validate that repo with defined name and namespace exists and return
        that repo. Otherwise fail with exception.  Creates dictionary for
        entity if it does not exist already.

        returns the repo for the repo_name.
        """
        if repo_name == "classes":
            if namespace not in self.classes:
                self.classes[namespace] = NocaseDict()
            return self.classes[namespace]

        elif repo_name == 'instances':
            if namespace not in self.instances:
                # This must be dict because key is CIMInstanceName
                self.instances[namespace] = {}
            return self.instances[namespace]

        elif repo_name == 'qualifiers':
            if namespace not in self.qualifiers:
                self.qualifiers[namespace] = NocaseDict()
            return self.qualifiers[namespace]

        elif repo_name == 'methods':
            if namespace not in self.methods:
                self.methods[namespace] = NocaseDict()
            return self.methods[namespace]

        assert False

    #####################################################################
    #
    #   Repository object access and create methods
    #
    #   These methods provide minimal confirmation of the CIM objects
    #   to assure that the data store is not corrupted. They should not
    #   be validators of object integrity.  That should be the role of
    #   the CIMRepository layer.
    #   This layer does not specifically define *args and **kwargs but
    #   assumes that the higher layer has validated the arguments
    #
    #####################################################################

    def EnumerateInstanceNames(self, *args, **kwargs):
        """This method is used by the MOF compiler only when it creates a
        namespace in the course of handling CIM_ERR_NAMESPACE_NOT_FOUND.
        Because the operations of this class silently create every namespace
        that is needed and never return that error, this method is never
        called, and is therefore not implemented.
        """

        raise CIMError(
            CIM_ERR_FAILED, 'This should not happen!',
            conn_id=self.conn_id)

    def DeleteInstance(self, *args, **kwargs):
        """This method is only invoked by :meth:`rollback` (on the underlying
        repository), and never by the MOF compiler, and is therefore not
        implemented."""

        raise CIMError(
            CIM_ERR_FAILED, 'This should not happen!',
            conn_id=self.conn_id)

    def GetClass(self, *args, **kwargs):
        """Retrieve a CIM class from the local repository of this class.

        For a description of the parameters, see
        :meth:`pywbem.WBEMConnection.GetClass`.
        """

        cname = args[0] if args else kwargs['ClassName']
        try:
            cc = self.classes[self.default_namespace][cname]
        except KeyError:
            if self.conn is None:
                ce = CIMError(CIM_ERR_NOT_FOUND, cname)
                raise ce
            cc = self.conn.GetClass(*args, **kwargs)
            try:
                self.classes[self.default_namespace][cc.classname] = cc
            except KeyError:
                self.classes[self.default_namespace] = \
                    NocaseDict({cc.classname: cc})

        # TODO should we be testing localonly, etc. here or above.
        if 'LocalOnly' in kwargs and not kwargs['LocalOnly']:
            if cc.superclass:
                try:
                    del kwargs['ClassName']
                except KeyError:
                    pass
                if args:
                    args = args[1:]
                super_ = self.GetClass(cc.superclass, *args, **kwargs)
                for prop in super_.properties.values():
                    if prop.name not in cc.properties:
                        cc.properties[prop.name] = prop
                for meth in super_.methods.values():
                    if meth.name not in cc.methods:
                        cc.methods[meth.name] = meth
        return cc

    def ModifyClass(self, *args, **kwargs):  # pylint: disable=no-self-use
        """This method is used by the MOF compiler only in the course of
        handling CIM_ERR_ALREADY_EXISTS after trying to create a class.
        Because :meth:`CreateClass` overwrites existing classes, this method
        is never called, and is therefore not implemented.
        """

        raise CIMError(
            CIM_ERR_FAILED, 'This should not happen!',
            conn_id=self.conn_id)

    def CreateClass(self, *args, **kwargs):
        """
        Override the CreateClass method in MOFWBEMConnection. NOTE: This is
        currently only used by the compiler.  The methods of Fake_WBEMConnectin
        go directly to the repository, not through this method.
        This modifies the overridden method to add validation.

        For a description of the parameters, see
        :meth:`pywbem.WBEMConnection.CreateClass`.
        """
        cc = args[0] if args else kwargs['NewClass']
        namespace = self.getns()

        try:
            self.compile_ordered_classnames.append(cc.classname)

            # The following generates an exception for each new ns
            self.classes[self.default_namespace][cc.classname] = cc
        except KeyError:
            self.classes[namespace] = \
                NocaseDict({cc.classname: cc})

        # Validate that references and embedded instance properties, methods,
        # etc. have classes that exist in repo. This  also institates the
        # mechanism that gets insures that prerequisite classes are inserted
        # into the repo.
        objects = list(cc.properties.values())
        for meth in cc.methods.values():
            objects += list(meth.parameters.values())

        for obj in objects:
            # Validate that reference_class exists in repo
            if obj.type == 'reference':
                try:
                    self.GetClass(obj.reference_class, LocalOnly=True,
                                  IncludeQualifiers=True)
                except CIMError as ce:
                    if ce.status_code == CIM_ERR_NOT_FOUND:
                        raise CIMError(
                            CIM_ERR_INVALID_PARAMETER,
                            _format("Class {0!A} referenced by element {1!A} "
                                    "of class {2!A} in namespace {3!A} does "
                                    "not exist",
                                    obj.reference_class, obj.name,
                                    cc.classname, self.getns()),
                            conn_id=self.conn_id)
                    raise

            elif obj.type == 'string':
                if 'EmbeddedInstance' in obj.qualifiers:
                    eiqualifier = obj.qualifiers['EmbeddedInstance']
                    try:
                        self.GetClass(eiqualifier.value, LocalOnly=True,
                                      IncludeQualifiers=False)
                    except CIMError as ce:
                        if ce.status_code == CIM_ERR_NOT_FOUND:
                            raise CIMError(
                                CIM_ERR_INVALID_PARAMETER,
                                _format("Class {0!A} specified by "
                                        "EmbeddInstance qualifier on element "
                                        "{1!A} of class {2!A} in namespace "
                                        "{3!A} does not exist",
                                        eiqualifier.value, obj.name,
                                        cc.classname, self.getns()),
                                conn_id=self.conn_id)
                        raise

        ccr = self.conn._resolve_class(  # pylint: disable=protected-access
            cc, namespace, self.qualifiers[namespace])
        if namespace not in self.classes:
            self.classes[namespace] = NocaseDict()
        self.classes[namespace][ccr.classname] = ccr

        try:
            self.class_names[namespace].append(ccr.classname)
        except KeyError:
            self.class_names[namespace] = [ccr.classname]

    def CreateInstance(self, *args, **kwargs):
        """
        Create a CIM instance in the local repository of this class.
        This method is derived from the the same method in the pywbem
        mof compiler but modified to:
        1. Use a dictionary as the container for instances where the
           key is the path. This means that all instances must have a
           path component to be inserted into the repository. Normally
           the path component is built within the compiler by using the
           instance alias.
        2. Fail with a CIMError exception if the instance already exists
           in the repository.

        For a description of the parameters, see
        :meth:`pywbem.WBEMConnection.CreateInstance`.
        """

        inst = args[0] if args else kwargs['NewInstance']

        # Get list of properties in class defined for this instance
        cln = inst.classname
        cls = self.GetClass(cln, IncludeQualifiers=True, LocalOnly=False)

        cls_key_properties = [p for p, v in cls.properties.items()
                              if 'key' in v.qualifiers]

        # Validate all key properties are in instance
        for pname in cls_key_properties:
            if pname not in inst.properties:
                raise CIMError(
                    CIM_ERR_INVALID_PARAMETER,
                    _format('CreateInstance failed. Key property {0!A}  in '
                            'class {1!A} but not in new_instance: {2!A}',
                            pname, cln, str(inst)))

        # Build path from instance and class
        if inst.path is None or not inst.path.keybindings:
            inst.path = CIMInstanceName.from_instance(
                cls, inst, namespace=self.default_namespace)

        if self.default_namespace not in self.instances:
            self.instances[self.default_namespace] = {}

        # exception if duplicate. NOTE: compiler overrides this with
        # modify instance.
        if inst.path in self.instances[self.default_namespace]:
            raise CIMError(
                CIM_ERR_ALREADY_EXISTS,
                _format('CreateInstance failed. Instance with path {0!A} '
                        'already exists in mock repository', inst.path))
        try:
            self.instances[self.default_namespace][inst.path] = inst
        except KeyError:
            self.instances[self.default_namespace] = {}
            self.instances[self.default_namespace][inst.path] = inst

        return inst.path

    def ModifyInstance(self, *args, **kwargs):
        """This method is used by the MOF compiler only in the course of
        handling CIM_ERR_ALREADY_EXISTS after trying to create an instance.

        NOTE: It does NOT support the propertylist attribute that is part
        of the CIM/XML defintion of ModifyInstance and it requires that
        each created instance include the instance path which means that
        the MOF must include the instance alias on each created instance.
        """
        mod_inst = args[0] if args else kwargs['ModifiedInstance']
        if self.default_namespace not in self.instances:
            raise CIMError(
                CIM_ERR_INVALID_NAMESPACE,
                _format('ModifyInstance failed. No instance repo exists. '
                        'Use compiler instance alias to set path on '
                        'instance declaration. inst: {0!A}', mod_inst))

        if mod_inst.path not in self.instances[self.default_namespace]:
            raise CIMError(
                CIM_ERR_NOT_FOUND,
                _format('ModifyInstance failed. No instance exists. '
                        'Use compiler instance alias to set path on '
                        'instance declaration. inst: {0!A}', mod_inst))

        orig_instance = self.instances[self.default_namespace][mod_inst.path]
        orig_instance.update(mod_inst.properties)
        self.instances[self.default_namespace][mod_inst.path] = orig_instance

    def _get_class(self, superclass, namespace=None,
                   local_only=False, include_qualifiers=True,
                   include_classorigin=True):
        """
        This method is just rename of GetClass to support same method
        with both MOFWBEMConnection and FakedWBEMConnection
        """
        return self.GetClass(superclass,
                             namespace=namespace,
                             local_only=local_only,
                             include_qualifiers=include_qualifiers,
                             include_classorigin=include_classorigin)

    def DeleteClass(self, *args, **kwargs):
        """This method is only invoked by :meth:`rollback` (on the underlying
        repository), and never by the MOF compiler, and is therefore not
        implemented."""

        raise CIMError(
            CIM_ERR_FAILED, 'This should not happen!',
            conn_id=self.conn_id)

    def EnumerateQualifiers(self, *args, **kwargs):
        """Enumerate the qualifier types in the local repository of this class.

        For a description of the parameters, see
        :meth:`pywbem.WBEMConnection.EnumerateQualifiers`.
        """

        if self.conn is not None:
            rv = self.conn.EnumerateQualifiers(*args, **kwargs)
        else:
            rv = []
        try:
            rv += list(self.qualifiers[self.default_namespace].values())
        except KeyError:
            pass
        return rv

    def GetQualifier(self, *args, **kwargs):
        """Retrieve a qualifier type from the local repository of this class.

        For a description of the parameters, see
        :meth:`pywbem.WBEMConnection.GetQualifier`.
        """

        qualname = args[0] if args else kwargs['QualifierName']
        try:
            qual = self.qualifiers[self.default_namespace][qualname]
        except KeyError:
            if self.conn is None:
                raise CIMError(
                    CIM_ERR_NOT_FOUND, qualname, conn_id=self.conn_id)
            qual = self.conn.GetQualifier(*args, **kwargs)
        return qual

    def SetQualifier(self, *args, **kwargs):
        """Create or modify a qualifier type in the local repository of this
        class.

        For a description of the parameters, see
        :meth:`pywbem.WBEMConnection.SetQualifier`.
        """

        qual = args[0] if args else kwargs['QualifierDeclaration']
        try:
            self.qualifiers[self.default_namespace][qual.name] = qual
        except KeyError:
            self.qualifiers[self.default_namespace] = \
                NocaseDict({qual.name: qual})

    def DeleteQualifier(self, *args, **kwargs):
        """This method is only invoked by :meth:`rollback` (on the underlying
        repository), and never by the MOF compiler, and is therefore not
        implemented."""

        raise CIMError(
            CIM_ERR_FAILED, 'This should not happen!',
            conn_id=self.conn_id)
