# -*- coding: utf-8 -*-

##############################################################################
#    Copyright (C) 2012 SICLIC http://siclic.fr
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
#############################################################################
from osv import fields, osv
from osv.orm import browse_null
import datetime as dt
from datetime import datetime, date, timedelta
from dateutil import *
from dateutil.tz import *

from copy import copy

class OpenbaseTag(osv.osv):
    _name = 'openbase.tag'
    _columns = {
        'name':fields.char('Value', size=128),
        'model':fields.char('Model', size=64),
        }

OpenbaseTag()

##Core abstract model to add SICLIC custom features, such as actions rights calculation (to be used in SICLIC custom GUI)
class OpenbaseCore(osv.Model):
    _auto = True
    _register = False # not visible in ORM registry, meant to be python-inherited only
    _transient = False # True in a TransientModel

    ##Internal use
    _actions_to_eval = {}
    ##Internal use
    _fields_names_to_eval = {}
    ##Attribute used to parse the 'actions' field.
    ##It's a dict, where the values are functions with the following signature : (cr, uid, record, groups_code)
    ## where 'record' is a browse_record of the current record, 'groups_code' is a list of the CODE of the groups_id of the current user
    _actions = {}
    ##Attribute used by the __init__ method to add specific fields.
    ##It's a dict : {'many2many_field': 'new_field'} where each 'new_field' will be created automatically, these fields return a list of [id,name_get()] using the many2many relationship
    _fields_names = {}
#    _fields_names_to_add = {'tags_names':'tags'}
    ##Internal use, define the fields to addfor each model inhering from OpenbaseCore
    _fields_names_to_add = {}

    #keywords to compute filter domain
    DATE_KEYWORDS = ['FIRSTDAYWEEK', 'LASTDAYWEEK',  'FIRSTDAYMONTH',  'LASTDAYMONTH', 'OVERMONTH', 'OUTDATED']
    DATE_FMT = "%Y-%m-%d"
    DATE_TIME_FMT = "%Y-%m-%d %H:%M:%S"

    ##Method used to compute 'actions' functionnal-field, this field is created for object inheriting from OpenbaseCore
    ## it uses the attribute '_actions' to parse the values. this attribute should be a dict, where the values are a function implementation with the following format : 
    ##    {'action1': lambda self, cr, uid, record, groups_code: record.state == 'draft'
    ## where 'record' is the browse_record of the current object, 'groups_code' is a list of string where each string is the 'code' value of the groups of the current user ('uid') 
    ## @return: List of String, where strings are actions authorized for the user for the records, using the _actions attribute definition 
    def _get_actions(self, cr, uid, ids, myFields ,arg, context=None):
        #default value: empty string for each id
        ret = {}.fromkeys(ids,'')
        groups_code = []
        groups_code = [group.code for group in self.pool.get("res.users").browse(cr, uid, uid, context=context).groups_id if group.code]

        for record in self.browse(cr, uid, ids, context=context):
            ret.update({record.id:[key for key,func in self._actions_to_eval[self._name].items() if func(self,cr,uid,record,groups_code)]})
        return ret

    _columns_to_add = {
        'actions':fields.function(_get_actions, method=True, string="Actions possibles",type="char", store=False),
        }

    
    ##@param uid: user who whants the metadata
    ##@return: dict containing number of records (that user can see),
    ##        model fields definition (another dict with field as key and list as definition),
    ##        @todo: filters authorized for this user too ?
    ##        in example : {'count':55, 'fields':{'name':{'string':'Kapweeee', type:'char', 'required':True}}, 'saved_filters': [TODO]}
    ##
    def getModelMetadata(self, cr, uid, context=None):
        if not context:
            context = self.pool.get('res.users').context_get(cr, uid, uid,)
        ret = {'count':0, 'fields':{'id':{'type':'integer'}}}

        #dict containing default keys to return, even if value is False (OpenERP does not return a key where the val is False)
        mandatory_vals = {'type':False,'required':False,'select':False,'readonly':False}
        #list containing key to return if set
        authorized_vals = ['selection','domain']
        vals_to_retrieve = authorized_vals + mandatory_vals.keys()

        #Get model id
        ret['model_id']  = self.pool.get('ir.model').search(cr, uid, [('model','=',self._name)])[0]


        #for each field, returns all mandatory fields, and return authorized fields if set
        for f, dict_vals in self.fields_get(cr, uid, context=context).items():
            final_val = mandatory_vals.copy()
            for key,val in dict_vals.items():
                if key in vals_to_retrieve:
                    final_val.update({key:val})
            ret['fields'].update({f:final_val})

        return ret
    
    ##Override the __init__ method to add 'actions' field to the model, and to add fields parsing the _field_names attribute
    ##field_names look like {'existing_field': 'new_field'} where 'existing_field' is *2many field and 'new_field' will be created, it returns a list of [id,name] of the related record
    def __init__(self, cr, pool):
        self._columns.update(self._columns_to_add)
        self._fields_names.update(self._fields_names_to_add)
        self._actions_to_eval.setdefault(self._name,{})
        self._fields_names_to_eval.setdefault(self._name,{})

        self._actions_to_eval[self._name].update(self._actions)
        self._fields_names_to_eval[self._name].update(self._fields_names)
        #method to retrieve many2many fields with custom format
        def _get_fields_names(self, cr, uid, ids, name, args, context=None):
            res = {}
            if not isinstance(name, list):
                name = [name]
            for obj in self.browse(cr, uid, ids, context=context):
                #for each field_names to read, retrieve their values
                res[obj.id] = {}
                for fname in name:
                    #many2many browse_record field to map
                    field_ids = obj[self._fields_names_to_eval[self._name][fname]]
                    if isinstance(field_ids, browse_null)== True :
                        continue
                    if not isinstance(field_ids, list):
                        field_ids = [field_ids]
                    val = []
                    for item in field_ids:
                        val.append([item.id,item.name_get()[0][1]])
                    res[obj.id].update({fname:val})
            return res

        super(OpenbaseCore,self).__init__(cr,pool)
        #then, add m2m openbase.tag to model
#        src = self._name.replace('.','_')
#        target = 'tag'
#        self._columns.update({'tags':fields.many2many('openbase.tag', '%s_%s_rel'%(src,target), src+'_id', target+'_id', 'Tags',
#                                                      context={'default_model':self._name}, domain=[('model','=',self._name)])})
        #add _field_names to fields definition of the model
        for f in self._fields_names.keys():
            #force name of new field with '_names' suffix
            self._columns.update({f:fields.function(_get_fields_names, type='char',method=True, multi='field_names',store=False)})

    ##Override of the std search() method to be able to parse domain with dynamic values defined in DATE_KEYWORDS
    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        new_args = []
        model_fields = self.fields_get(cr, uid, context=context)
        #fields = self.fields_get(cr, uid, context=context).items()
        for id, domain  in enumerate(args) :
            #Test if domain tuple = ('key','operator','value')
            if len(domain) == 3 :
                #Get key, operator and domain
                k, o, v = domain
                #Get field's type
                try:
                    type = self._columns[k]._type
                except (KeyError):
                    type = None
                #if domain contains special keyword
                if v in self.DATE_KEYWORDS :
                    #For records filters : Adapts keyword in domain to specials filter that need to be computed (cf get_date_from_keyword method)
                    domain[2] = self.get_date_from_keyword(v)
                #if model has 'complete_name' field
                elif domain[0]== 'name' and 'complete_name' in model_fields and (model_fields['complete_name'].get('selectable',False)):
                    #add domain on 'complete_name'
                    new_domain = list(domain)
                    new_domain[0] = 'complete_name'
                    new_args.insert(0,'|')
                    new_args.extend([new_domain])
                elif  type != None and type == 'datetime':
                    try:
                        #Test if already format with hours
                        datetime.strptime(v,self.DATE_TIME_FMT)
                    except ValueError:
                        #Format date with hours
                        domain[2] = datetime.strftime(datetime.strptime(v,self.DATE_FMT), "%Y-%m-%d %H:%M:%S")
                        #if equal method in domain : build domain, example : [('date_to_compare', '>' ,'2014-03-05 00:00:00'), ('date_to_compare', '<' ,'2014-03-05 23:59:59')]
                        if domain[1] ==  "=":
                            #prepare first domain , example : [('date_to_compare', '>' ,'2014-03-05 00:00:00')]
                            domain[1] = ">"
                            #prepare second domain , example : [('date_to_compare', '<' ,'2014-03-05 23:59:59')]
                            new_domain = copy(domain)
                            new_domain[1] = "<"
                            new_domain[2] = datetime.strftime(datetime.strptime(v,self.DATE_FMT), "%Y-%m-%d 23:59:59")
                            new_args.extend([new_domain])
            new_args.extend([domain])

        return super(OpenbaseCore, self).search(cr, uid, new_args, offset, limit, order, context, count)

    ## Override of standard read() method, to force 'user-context' to be computed if not yet defined
    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read' ):
        if not context :
            context = self.pool.get('res.users').context_get(cr, uid, uid)
        return super(OpenbaseCore, self).read(cr, uid, ids, fields, context=context, load=load)
    
    ##@param keyword: keyword to compute corresponding date
    ##@return: return string date for domain search
    ##    domain is used to filter OpenBase object (ask (request), project (intervention)  :
    ##    * from current week
    ##    * from current month
    ##    * delayed (deadline spent)
    def get_date_from_keyword(self, keyword):
        val = ""
        timeDtFrmt = "%Y-%m-%d %H:%M:%S"
        today = date.today()
        start_day_month = dt.datetime(today.year, today.month, 1)
        dates = [today + dt.timedelta(days=i) for i in range(0 - today.weekday(), 7 - today.weekday())]
        if keyword == 'FIRSTDAYWEEK':
             return datetime.strftime(dates[0],timeDtFrmt)
        elif keyword == 'LASTDAYWEEK':
             return datetime.strftime(dates[6],timeDtFrmt)
        elif keyword == 'FIRSTDAYMONTH':
            return datetime.strftime(dt.datetime(today.year, today.month, 1),timeDtFrmt)
        elif keyword == 'LASTDAYMONTH':
            date_on_next_month = start_day_month + dt.timedelta(31)
            start_next_month = dt.datetime(date_on_next_month.year, date_on_next_month.month, 1)
            return datetime.strftime(start_next_month - dt.timedelta(1),timeDtFrmt)
        elif keyword == 'OVERMONTH':
             return datetime.strftime(start_day_month + dt.timedelta(31),timeDtFrmt)
        elif keyword == 'OUTDATED':
            return datetime.strftime(today,timeDtFrmt)
        return val
    
    ##Implements standard method to send a mail with OpenERP.
    ## @param id: the object id on which to parse the mail
    ## @param vals: dict ({'state':[]}) where 'state' defining which mail should be sent (used to retrieve the corresponding mail_template)
    ## @param module: the module of the template to be parsed
    ## @param mail_templates: the template(s) available for this object
    def send_mail(self, cr, uid, id, vals, module, model, mail_templates):
        email_obj = self.pool.get("email.template")
        email_tmpl_id = 0
        data_obj = self.pool.get('ir.model.data')
        #first, retrieve template_id according to 'state' parameter
        if vals.get('state','') in mail_templates.keys():
            email_tmpl_id = data_obj.get_object_reference(cr, uid, module,mail_templates.get(vals.get('state')))[1]
            if email_tmpl_id:
                if isinstance(email_tmpl_id, list):
                    email_tmpl_id = email_tmpl_id[0]
                #generate mail and send it
                mail_id = email_obj.send_mail(cr, uid, email_tmpl_id, id)
                self.pool.get("mail.message").write(cr, uid, [mail_id], {})
                self.pool.get("mail.message").send(cr, uid, [mail_id])

class OpenbaseCoreWizard(OpenbaseCore):
    _auto = True
    _register = False # not visible in ORM registry, meant to be python-inherited only
    _transient = True # True in a TransientModel
