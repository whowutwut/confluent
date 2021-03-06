# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2014 IBM Corporation
# Copyright 2015-2018 Lenovo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# concept here that mapping from the resource tree and arguments go to
# specific python class signatures.  The intent is to require
# plugin authors to come here if they *really* think they need new 'commands'
# and hopefully curtail deviation by each plugin author

# have to specify a standard place for cfg selection of *which* plugin
# as well a standard to map api requests to python funcitons
# e.g. <nodeelement>/power/state maps to some plugin
# HardwareManager.get_power/set_power selected by hardwaremanagement.method
# plugins can advertise a set of names if there is a desire for readable things
# exceptions to handle os images
# endpoints point to a class... usually, the class should have:
# -create
# -retrieve
# -update
# -delete
# functions.  Console is special and just get's passed through
# see API.txt

import confluent
import confluent.alerts as alerts
import confluent.log as log
import confluent.tlvdata as tlvdata
import confluent.config.attributes as attrscheme
import confluent.config.configmanager as cfm
import confluent.collective.manager as collective
import confluent.discovery.core as disco
import confluent.interface.console as console
import confluent.exceptions as exc
import confluent.messages as msg
import confluent.networking.macmap as macmap
import confluent.noderange as noderange
try:
    import confluent.shellmodule as shellmodule
except ImportError:
    pass
try:
    import OpenSSL.crypto as crypto
except ImportError:
    # Only required for collective mode
    crypto = None
import confluent.util as util
import eventlet.greenpool as greenpool
import eventlet.green.ssl as ssl
import eventlet.queue as queue
import itertools
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
import socket
import struct
import sys

pluginmap = {}
dispatch_plugins = (b'ipmi', u'ipmi')


def seek_element(currplace, currkey):
    try:
        return currplace[currkey]
    except TypeError:
        if isinstance(currplace, PluginCollection):
            # we hit a plugin curated collection, all children
            # are up to the plugin to comprehend
            return currplace
        raise


def nested_lookup(nestdict, key):
    try:
        return reduce(seek_element, key, nestdict)
    except TypeError:
        raise exc.NotFoundException("Invalid element requested")


def load_plugins():
    # To know our plugins directory, we get the parent path of 'bin'
    _init_core()
    path = os.path.dirname(os.path.realpath(__file__))
    plugintop = os.path.realpath(os.path.join(path, 'plugins'))
    plugins = set()
    for plugindir in os.listdir(plugintop):
        plugindir = os.path.join(plugintop, plugindir)
        if not os.path.isdir(plugindir):
            continue
        sys.path.insert(1, plugindir)
        # two passes, to avoid adding both py and pyc files
        for plugin in os.listdir(plugindir):
            if plugin.startswith('.'):
                continue
            (plugin, plugtype) = os.path.splitext(plugin)
            if plugtype == '.sh':
                pluginmap[plugin] = shellmodule.Plugin(
                    os.path.join(plugindir, plugin + '.sh'))
            elif "__init__" not in plugin:
                plugins.add(plugin)
        for plugin in plugins:
            tmpmod = __import__(plugin)
            if 'plugin_names' in tmpmod.__dict__:
                for name in tmpmod.plugin_names:
                    pluginmap[name] = tmpmod
            else:
                pluginmap[plugin] = tmpmod
        # restore path to not include the plugindir
        sys.path.pop(1)


rootcollections = ['discovery/', 'events/', 'networking/',
                   'noderange/', 'nodes/', 'nodegroups/', 'users/', 'version']


class PluginRoute(object):
    def __init__(self, routedict):
        self.routeinfo = routedict


class PluginCollection(object):
    def __init__(self, routedict):
        self.routeinfo = routedict

def _init_core():
    global noderesources
    global nodegroupresources
    import confluent.shellserver as shellserver
    # _ prefix indicates internal use (e.g. special console scheme) and should not
    # be enumerated in any collection
    noderesources = {
        'attributes': {
            'all': PluginRoute({'handler': 'attributes'}),
            'current': PluginRoute({'handler': 'attributes'}),
            'expression': PluginRoute({'handler': 'attributes'}),
        },
        'boot': {
            'nextdevice': PluginRoute({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),
        },
        'configuration': {
            'management_controller': {
                'alerts': {
                    'destinations': PluginCollection({
                        'pluginattrs': ['hardwaremanagement.method'],
                        'default': 'ipmi',
                    }),
                },
                'users': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'licenses': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'net_interfaces': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'reset': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'hostname': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'identifier': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'domain_name': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'ntp': {
                    'enabled': PluginRoute({
                        'pluginattrs': ['hardwaremanagement.method'],
                        'default': 'ipmi',
                    }),
                    'servers': PluginCollection({
                        'pluginattrs': ['hardwaremanagement.method'],
                        'default': 'ipmi',
                    }),
                },
            },
            'storage': {
                'all': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'arrays': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'disks': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'volumes': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                })
            },
            'system': {
                'all': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'advanced': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'clear': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                })
            },
        },
        '_console': {
            'session': PluginRoute({
                'pluginattrs': ['console.method'],
            }),
        },
        '_shell': {
            'session': PluginRoute({
                # For now, not configurable, wait until there's demand
                'handler': 'ssh',
            }),
        },
        '_enclosure': {
            'reseat_bay': PluginRoute(
                {'pluginattrs': ['hardwaremanagement.method'],
                 'default': 'ipmi'}),
        },
        'shell': {
            # another special case similar to console
            'sessions': PluginCollection({
                    'handler': shellserver,
            }),
        },
        'console': {
            # this is a dummy value, http or socket must handle special
            'session': None,
            'license': PluginRoute({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),
        },
        'description': PluginRoute({
            'pluginattrs': ['hardwaremanagement.method'],
            'default': 'ipmi',
        }),
        'events': {
            'hardware': {
                'log': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'decode': PluginRoute({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
            },
        },
        #'forward': {
        #    # Another dummy value, currently only for the gui
        #    'web': None,
        #},
        'health': {
            'hardware': PluginRoute({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),
        },
        'identify': PluginRoute({
            'pluginattrs': ['hardwaremanagement.method'],
            'default': 'ipmi',
        }),
        'inventory': {
            'hardware': {
                'all': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
            },
            'firmware': {
                'all': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'updates': {
                    'active': PluginCollection({
                            'pluginattrs': ['hardwaremanagement.method'],
                            'default': 'ipmi',
                    }),
                },
            },
        },
        'media': {
            'uploads': PluginCollection({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),
            'attach': PluginRoute({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),
            'detach': PluginRoute({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),
            'current': PluginRoute({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),

        },
        'power': {
            'state': PluginRoute({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),
            'reseat':  PluginRoute({'handler': 'enclosure'}),
        },
        'sensors': {
            'hardware': {
                'all': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'energy': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'temperature': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'power': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'fans': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
                'leds': PluginCollection({
                    'pluginattrs': ['hardwaremanagement.method'],
                    'default': 'ipmi',
                }),
            },

        },
        'support': {
            'servicedata': PluginCollection({
                'pluginattrs': ['hardwaremanagement.method'],
                'default': 'ipmi',
            }),
        },
    }

    nodegroupresources = {
        'attributes': {
            'all': PluginRoute({'handler': 'attributes'}),
            'current': PluginRoute({'handler': 'attributes'}),
        },
    }


def create_user(inputdata, configmanager):
    try:
        username = inputdata['name']
        del inputdata['name']
    except (KeyError, ValueError):
        raise exc.InvalidArgumentException()
    configmanager.create_user(username, attributemap=inputdata)


def update_user(name, attribmap, configmanager):
    try:
        configmanager.set_user(name, attribmap)
    except ValueError:
        raise exc.InvalidArgumentException()


def show_user(name, configmanager):
    userobj = configmanager.get_user(name)
    rv = {}
    for attr in attrscheme.user.iterkeys():
        rv[attr] = None
        if attr == 'password':
            if 'cryptpass' in userobj:
                rv['password'] = {'cryptvalue': True}
            yield msg.CryptedAttributes(kv={'password': rv['password']},
                                        desc=attrscheme.user[attr][
                                            'description'])
        else:
            if attr in userobj:
                rv[attr] = userobj[attr]
            yield msg.Attributes(kv={attr: rv[attr]},
                                 desc=attrscheme.user[attr]['description'])


def stripnode(iterablersp, node):
    for i in iterablersp:
        if i is None:
            raise exc.NotImplementedException("Not Implemented")
        i.strip_node(node)
        yield i


def iterate_collections(iterable, forcecollection=True):
    for coll in iterable:
        if forcecollection and coll[-1] != '/':
            coll += '/'
        yield msg.ChildCollection(coll, candelete=True)


def iterate_resources(fancydict):
    for resource in fancydict:
        if resource.startswith("_"):
            continue
        if resource == 'abbreviate':
            pass
        elif not isinstance(fancydict[resource], PluginRoute):  # a resource
            resource += '/'
        yield msg.ChildCollection(resource)


def delete_user(user, configmanager):
    configmanager.del_user(user)
    yield msg.DeletedResource(user)


def delete_nodegroup_collection(collectionpath, configmanager):
    if len(collectionpath) == 2:  # just the nodegroup
        group = collectionpath[-1]
        configmanager.del_groups([group])
        yield msg.DeletedResource(group)
    else:
        raise Exception("Not implemented")


def delete_node_collection(collectionpath, configmanager, isnoderange):
    if len(collectionpath) == 2:  # just node
        nodes = [collectionpath[-1]]
        if isnoderange:
            nodes = noderange.NodeRange(nodes[0], configmanager).nodes
        configmanager.del_nodes(nodes)
        for node in nodes:
            yield msg.DeletedResource(node)
    else:
        raise Exception("Not implemented")


def enumerate_nodegroup_collection(collectionpath, configmanager):
    nodegroup = collectionpath[1]
    if not configmanager.is_nodegroup(nodegroup):
        raise exc.NotFoundException(
            'Invalid nodegroup: {0} not found'.format(nodegroup))
    del collectionpath[0:2]
    collection = nested_lookup(nodegroupresources, collectionpath)
    return iterate_resources(collection)


def enumerate_node_collection(collectionpath, configmanager):
    if collectionpath == ['nodes']:  # it is just '/node/', need to list nodes
        allnodes = list(configmanager.list_nodes())
        try:
            allnodes.sort(key=noderange.humanify_nodename)
        except TypeError:
            allnodes.sort()
        return iterate_collections(allnodes)
    nodeorrange = collectionpath[1]
    if collectionpath[0] == 'nodes' and not configmanager.is_node(nodeorrange):
        raise exc.NotFoundException("Invalid element requested")
    collection = nested_lookup(noderesources, collectionpath[2:])
    if len(collectionpath) == 2 and collectionpath[0] == 'noderange':
        collection['nodes'] = {}
        collection['abbreviate'] = {}
    if not isinstance(collection, dict):
        raise exc.NotFoundException("Invalid element requested")
    return iterate_resources(collection)


def create_group(inputdata, configmanager):
    try:
        groupname = inputdata['name']
        del inputdata['name']
        attribmap = {groupname: inputdata}
    except KeyError:
        raise exc.InvalidArgumentException()
    try:
        configmanager.add_group_attributes(attribmap)
    except ValueError as e:
        raise exc.InvalidArgumentException(str(e))
    yield msg.CreatedResource(groupname)


def create_node(inputdata, configmanager):
    try:
        nodename = inputdata['name']
        del inputdata['name']
        attribmap = {nodename: inputdata}
    except KeyError:
        raise exc.InvalidArgumentException('name not specified')
    try:
        configmanager.add_node_attributes(attribmap)
    except ValueError as e:
        raise exc.InvalidArgumentException(str(e))
    yield msg.CreatedResource(nodename)


def create_noderange(inputdata, configmanager):
    try:
        noder = inputdata['name']
        del inputdata['name']
        attribmap = {}
        for node in noderange.NodeRange(noder).nodes:
            attribmap[node] = inputdata
    except KeyError:
        raise exc.InvalidArgumentException('name not specified')
    try:
        configmanager.add_node_attributes(attribmap)
    except ValueError as e:
        raise exc.InvalidArgumentException(str(e))
    for node in attribmap:
        yield msg.CreatedResource(node)



def enumerate_collections(collections):
    for collection in collections:
        yield msg.ChildCollection(collection)


def handle_nodegroup_request(configmanager, inputdata,
                             pathcomponents, operation):
    iscollection = False
    routespec = None
    if len(pathcomponents) < 2:
        if operation == "create":
            inputdata = msg.InputAttributes(pathcomponents, inputdata)
            return create_group(inputdata.attribs, configmanager)
        allgroups = list(configmanager.get_groups())
        try:
            allgroups.sort(key=noderange.humanify_nodename)
        except TypeError:
            allgroups.sort()
        return iterate_collections(allgroups)
    elif len(pathcomponents) == 2:
        iscollection = True
    else:
        try:
            routespec = nested_lookup(nodegroupresources, pathcomponents[2:])
            if isinstance(routespec, dict):
                iscollection = True
            elif isinstance(routespec, PluginCollection):
                iscollection = False  # it is a collection, but plugin defined
        except KeyError:
            raise exc.NotFoundException("Invalid element requested")
    if iscollection:
        if operation == "delete":
            return delete_nodegroup_collection(pathcomponents,
                                               configmanager)
        elif operation == "retrieve":
            return enumerate_nodegroup_collection(pathcomponents,
                                                  configmanager)
        else:
            raise Exception("TODO")
    plugroute = routespec.routeinfo
    inputdata = msg.get_input_message(
        pathcomponents[2:], operation, inputdata)
    if 'handler' in plugroute:  # fixed handler definition
        hfunc = getattr(pluginmap[plugroute['handler']], operation)
        return hfunc(
            nodes=None, element=pathcomponents,
            configmanager=configmanager,
            inputdata=inputdata)
    raise Exception("unknown case encountered")


class BadPlugin(object):
    def __init__(self, node, plugin):
        self.node = node
        self.plugin = plugin

    def error(self, *args, **kwargs):
        yield msg.ConfluentNodeError(
            self.node, self.plugin + ' is not a supported plugin')


class BadCollective(object):
    def __init__(self, node):
        self.node = node

    def error(self, *args, **kwargs):
        yield msg.ConfluentNodeError(
            self.node, 'collective mode is active, but collective.manager '
                       'is not set for this node')

def abbreviate_noderange(configmanager, inputdata, operation):
    if operation != 'create':
        raise exc.InvalidArgumentException('Must be a create with nodes in list')
    if 'nodes' not in inputdata:
        raise exc.InvalidArgumentException('Must be given list of nodes under key named nodes')
    if isinstance(inputdata['nodes'], str) or isinstance(inputdata['nodes'], unicode):
        inputdata['nodes'] = inputdata['nodes'].split(',')
    return (msg.KeyValueData({'noderange': noderange.ReverseNodeRange(inputdata['nodes'], configmanager).noderange}),)


def handle_dispatch(connection, cert, dispatch, peername):
    cert = crypto.dump_certificate(crypto.FILETYPE_ASN1, cert)
    if not util.cert_matches(
            cfm.get_collective_member(peername)['fingerprint'], cert):
        connection.close()
        return
    dispatch = pickle.loads(dispatch)
    configmanager = cfm.ConfigManager(dispatch['tenant'])
    nodes = dispatch['nodes']
    inputdata = dispatch['inputdata']
    operation = dispatch['operation']
    pathcomponents = dispatch['path']
    routespec = nested_lookup(noderesources, pathcomponents)
    plugroute = routespec.routeinfo
    plugpath = None
    nodesbyhandler = {}
    passvalues = []
    nodeattr = configmanager.get_node_attributes(
        nodes, plugroute['pluginattrs'])
    for node in nodes:
        for attrname in plugroute['pluginattrs']:
            if attrname in nodeattr[node]:
                plugpath = nodeattr[node][attrname]['value']
            elif 'default' in plugroute:
                plugpath = plugroute['default']
        if plugpath:
            try:
                hfunc = getattr(pluginmap[plugpath], operation)
            except KeyError:
                nodesbyhandler[BadPlugin(node, plugpath).error] = [node]
                continue
            if hfunc in nodesbyhandler:
                nodesbyhandler[hfunc].append(node)
            else:
                nodesbyhandler[hfunc] = [node]
    try:
        for hfunc in nodesbyhandler:
            passvalues.append(hfunc(
                nodes=nodesbyhandler[hfunc], element=pathcomponents,
                configmanager=configmanager,
                inputdata=inputdata))
        for res in itertools.chain(*passvalues):
            _forward_rsp(connection, res)
    except Exception as res:
        _forward_rsp(connection, res)
    connection.sendall('\x00\x00\x00\x00\x00\x00\x00\x00')


def _forward_rsp(connection, res):
    r = pickle.dumps(res)
    rlen = len(r)
    if not rlen:
        return
    connection.sendall(struct.pack('!Q', rlen))
    connection.sendall(r)


def handle_node_request(configmanager, inputdata, operation,
                        pathcomponents, autostrip=True):
    if log.logfull:
        raise exc.TargetResourceUnavailable('Filesystem full, free up space and restart confluent service')
    iscollection = False
    routespec = None
    if pathcomponents[0] == 'noderange':
        if len(pathcomponents) > 3 and pathcomponents[2] == 'nodes':
            # transform into a normal looking node request
            # this does mean we don't see if it is a valid
            # child, but that's not a goal for the noderange
            # facility anyway
            isnoderange = False
            pathcomponents = pathcomponents[2:]
        elif len(pathcomponents) == 3 and pathcomponents[2] == 'abbreviate':
            return abbreviate_noderange(configmanager, inputdata, operation)
        else:
            isnoderange = True
    else:
        isnoderange = False
    try:
        nodeorrange = pathcomponents[1]
        if not isnoderange and not configmanager.is_node(nodeorrange):
            raise exc.NotFoundException("Invalid Node")
        if isnoderange and not (len(pathcomponents) == 3 and
                                        pathcomponents[2] == 'abbreviate'):
            try:
                nodes = noderange.NodeRange(nodeorrange, configmanager).nodes
            except Exception as e:
                raise exc.NotFoundException("Invalid Noderange: " + str(e))
        else:
            nodes = (nodeorrange,)
    except IndexError:  # doesn't actually have a long enough path
        # this is enumerating a list of nodes or just empty noderange
        if isnoderange and operation == "retrieve":
            return iterate_collections([])
        elif isnoderange and operation == "create":
            inputdata = msg.InputAttributes(pathcomponents, inputdata)
            return create_noderange(inputdata.attribs, configmanager)
        elif isnoderange or operation == "delete":
            raise exc.InvalidArgumentException()
        if operation == "create":
            inputdata = msg.InputAttributes(pathcomponents, inputdata)
            return create_node(inputdata.attribs, configmanager)
        allnodes = list(configmanager.list_nodes())
        try:
            allnodes.sort(key=noderange.humanify_nodename)
        except TypeError:
            allnodes.sort()
        return iterate_collections(allnodes)
    if (isnoderange and len(pathcomponents) == 3 and
            pathcomponents[2] == 'nodes'):
        # this means that it's a list of relevant nodes
        nodes = list(nodes)
        try:
            nodes.sort(key=noderange.humanify_nodename)
        except TypeError:
            nodes.sort()
        return iterate_collections(nodes)
    if len(pathcomponents) == 2:
        iscollection = True
    else:
        try:
            routespec = nested_lookup(noderesources, pathcomponents[2:])
        except KeyError:
            raise exc.NotFoundException("Invalid element requested")
        if isinstance(routespec, dict):
            iscollection = True
        elif isinstance(routespec, PluginCollection):
            iscollection = False  # it is a collection, but plugin defined
        elif routespec is None:
            raise exc.InvalidArgumentException('Custom interface required for resource')
    if iscollection:
        if operation == "delete":
            return delete_node_collection(pathcomponents, configmanager,
                                          isnoderange)
        elif operation == "retrieve":
            return enumerate_node_collection(pathcomponents, configmanager)
        else:
            raise Exception("TODO here")
    del pathcomponents[0:2]
    passvalues = queue.Queue()
    plugroute = routespec.routeinfo
    inputdata = msg.get_input_message(
        pathcomponents, operation, inputdata, nodes, isnoderange,
        configmanager)
    if 'handler' in plugroute:  # fixed handler definition, easy enough
        if isinstance(plugroute['handler'], str):
            hfunc = getattr(pluginmap[plugroute['handler']], operation)
        else:
            hfunc = getattr(plugroute['handler'], operation)
        passvalue = hfunc(
            nodes=nodes, element=pathcomponents,
            configmanager=configmanager,
            inputdata=inputdata)
        if isnoderange:
            return passvalue
        elif isinstance(passvalue, console.Console):
            return [passvalue]
        else:
            return stripnode(passvalue, nodes[0])
    elif 'pluginattrs' in plugroute:
        nodeattr = configmanager.get_node_attributes(
            nodes, plugroute['pluginattrs'] + ['collective.manager'])
        plugpath = None
        nodesbymanager = {}
        nodesbyhandler = {}
        badcollnodes = []
        for node in nodes:
            for attrname in plugroute['pluginattrs']:
                if attrname in nodeattr[node]:
                    plugpath = nodeattr[node][attrname]['value']
                elif 'default' in plugroute:
                    plugpath = plugroute['default']
            if plugpath in dispatch_plugins:
                cfm.check_quorum()
                manager = nodeattr[node].get('collective.manager', {}).get(
                    'value', None)
                if manager:
                    if collective.get_myname() != manager:
                        if manager not in nodesbymanager:
                            nodesbymanager[manager] = set([node])
                        else:
                            nodesbymanager[manager].add(node)
                        continue
                elif list(cfm.list_collective()):
                    badcollnodes.append(node)
                    continue
            if plugpath:
                try:
                    hfunc = getattr(pluginmap[plugpath], operation)
                except KeyError:
                    nodesbyhandler[BadPlugin(node, plugpath).error] = [node]
                    continue
                if hfunc in nodesbyhandler:
                    nodesbyhandler[hfunc].append(node)
                else:
                    nodesbyhandler[hfunc] = [node]
        for bn in badcollnodes:
            nodesbyhandler[BadCollective(bn).error] = [bn]
        workers = greenpool.GreenPool()
        numworkers = 0
        for hfunc in nodesbyhandler:
            numworkers += 1
            workers.spawn(addtoqueue, passvalues, hfunc, {'nodes': nodesbyhandler[hfunc],
                                           'element': pathcomponents,
                'configmanager': configmanager,
                'inputdata': inputdata})
        for manager in nodesbymanager:
            numworkers += 1
            workers.spawn(addtoqueue, passvalues, dispatch_request, {
                'nodes': nodesbymanager[manager], 'manager': manager,
                'element': pathcomponents, 'configmanager': configmanager,
                'inputdata': inputdata, 'operation': operation})
        if isnoderange or not autostrip:
            return iterate_queue(numworkers, passvalues)
        else:
            if numworkers > 0:
                return iterate_queue(numworkers, passvalues, nodes[0])
            else:
                raise exc.NotImplementedException()

        # elif isinstance(passvalues[0], console.Console):
        #     return passvalues[0]
        # else:
        #     return stripnode(passvalues[0], nodes[0])


def iterate_queue(numworkers, passvalues, strip=False):
    completions = 0
    while completions < numworkers:
        nv = passvalues.get()
        if nv == 'theend':
            completions += 1
        else:
            if isinstance(nv, Exception):
                raise nv
            if strip and not isinstance(nv, console.Console):
                nv.strip_node(strip)
            yield nv


def addtoqueue(theq, fun, kwargs):
    try:
        result = fun(**kwargs)
        if isinstance(result, console.Console):
            theq.put(result)
        else:
            for pv in result:
                theq.put(pv)
    except Exception as e:
        theq.put(e)
    finally:
        theq.put('theend')


def dispatch_request(nodes, manager, element, configmanager, inputdata,
                     operation):
    a = configmanager.get_collective_member(manager)
    try:
        remote = socket.create_connection((a['address'], 13001))
        remote.settimeout(90)
        remote = ssl.wrap_socket(remote, cert_reqs=ssl.CERT_NONE,
                                 keyfile='/etc/confluent/privkey.pem',
                                 certfile='/etc/confluent/srvcert.pem')
    except Exception:
        for node in nodes:
            if a:
                yield msg.ConfluentResourceUnavailable(
                    node, 'Collective member {0} is unreachable'.format(
                        a['name']))
            else:
                yield msg.ConfluentResourceUnavailable(
                    node,
                    '"{0}" is not recognized as a collective member'.format(
                        manager))

        return
    if not util.cert_matches(a['fingerprint'], remote.getpeercert(
            binary_form=True)):
        raise Exception("Invalid certificate on peer")
    tlvdata.recv(remote)
    tlvdata.recv(remote)
    myname = collective.get_myname()
    dreq = pickle.dumps({'name': myname, 'nodes': list(nodes),
                         'path': element,'tenant': configmanager.tenant,
                         'operation': operation, 'inputdata': inputdata})
    tlvdata.send(remote, {'dispatch': {'name': myname, 'length': len(dreq)}})
    remote.sendall(dreq)
    while True:
        try:
            rlen = remote.recv(8)
        except Exception:
            for node in nodes:
                yield msg.ConfluentResourceUnavailable(
                    node, 'Collective member {0} went unreachable'.format(
                        a['name']))
            return
        while len(rlen) < 8:
            try:
                nlen = remote.recv(8 - len(rlen))
            except Exception:
                nlen = 0
            if not nlen:
                for node in nodes:
                    yield msg.ConfluentResourceUnavailable(
                        node, 'Collective member {0} went unreachable'.format(
                            a['name']))
                return
            rlen += nlen
        rlen = struct.unpack('!Q', rlen)[0]
        if rlen == 0:
            break
        try:
            rsp = remote.recv(rlen)
        except Exception:
            for node in nodes:
                yield msg.ConfluentResourceUnavailable(
                    node, 'Collective member {0} went unreachable'.format(
                        a['name']))
            return
        while len(rsp) < rlen:
            try:
                nrsp = remote.recv(rlen - len(rsp))
            except Exception:
                nrsp = 0
            if not nrsp:
                for node in nodes:
                    yield msg.ConfluentResourceUnavailable(
                        node, 'Collective member {0} went unreachable'.format(
                            a['name']))
                return
            rsp += nrsp
        rsp = pickle.loads(rsp)
        if isinstance(rsp, Exception):
            raise rsp
        yield rsp


def handle_discovery(pathcomponents, operation, configmanager, inputdata):
    if pathcomponents[0] == 'detected':
        pass

def handle_discovery(pathcomponents, operation, configmanager, inputdata):
    if pathcomponents[0] == 'detected':
        pass

def handle_path(path, operation, configmanager, inputdata=None, autostrip=True):
    """Given a full path request, return an object.

    The plugins should generally return some sort of iterator.
    An exception is made for console/session, which should return
    a class with connect(), read(), write(bytes), and close()
    """
    pathcomponents = path.split('/')
    del pathcomponents[0]  # discard the value from leading /
    if pathcomponents[-1] == '':
        del pathcomponents[-1]
    if not pathcomponents:  # root collection list
        return enumerate_collections(rootcollections)
    elif pathcomponents[0] == 'noderange':
        return handle_node_request(configmanager, inputdata, operation,
                                   pathcomponents, autostrip)
    elif pathcomponents[0] == 'nodegroups':
        return handle_nodegroup_request(configmanager, inputdata,
                                        pathcomponents,
                                        operation)
    elif pathcomponents[0] == 'nodes':
        # single node request of some sort
        return handle_node_request(configmanager, inputdata,
                                   operation, pathcomponents, autostrip)
    elif pathcomponents[0] == 'discovery':
        return disco.handle_api_request(
            configmanager, inputdata, operation, pathcomponents)
    elif pathcomponents[0] == 'networking':
        return macmap.handle_api_request(
            configmanager, inputdata, operation, pathcomponents)
    elif pathcomponents[0] == 'version':
        return (msg.Attributes(kv={'version': confluent.__version__}),)
    elif pathcomponents[0] == 'users':
        # TODO: when non-administrator accounts exist,
        # they must only be allowed to see their own user
        try:
            user = pathcomponents[1]
        except IndexError:  # it's just users/
            if operation == 'create':
                inputdata = msg.get_input_message(
                    pathcomponents, operation, inputdata,
                    configmanager=configmanager)
                create_user(inputdata.attribs, configmanager)
            return iterate_collections(configmanager.list_users(),
                                       forcecollection=False)
        if user not in configmanager.list_users():
            raise exc.NotFoundException("Invalid user %s" % user)
        if operation == 'retrieve':
            return show_user(user, configmanager)
        elif operation == 'delete':
            return delete_user(user, configmanager)
        elif operation == 'update':
            inputdata = msg.get_input_message(
                pathcomponents, operation, inputdata,
                configmanager=configmanager)
            update_user(user, inputdata.attribs, configmanager)
            return show_user(user, configmanager)
    elif pathcomponents[0] == 'events':
        try:
            element = pathcomponents[1]
        except IndexError:
            if operation != 'retrieve':
                raise exc.InvalidArgumentException('Target is read-only')
            return (msg.ChildCollection('decode'),)
        if element != 'decode':
            raise exc.NotFoundException()
        if operation == 'update':
            return alerts.decode_alert(inputdata, configmanager)
    elif pathcomponents[0] == 'discovery':
        return handle_discovery(pathcomponents[1:], operation, configmanager,
                                inputdata)
    else:
        raise exc.NotFoundException()
