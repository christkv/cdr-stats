#
# CDR-Stats License
# http://www.cdr-stats.org
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2011-2012 Star2Billing S.L.
#
# The Initial Developer of the Original Code is
# Arezqui Belaid <info@star2billing.com>
#
from django.conf import settings
from celery.task import Task, PeriodicTask
from celery.decorators import task, periodic_task
from cdr.import_cdr import import_cdr
from cdr.import_cdr_asterisk_mysql import import_cdr_asterisk_mysql
from cdr.common_tasks import single_instance_task
from datetime import timedelta
import datetime
import sqlite3

LOCK_EXPIRE = 60 * 30 # Lock expires in 30 minutes


class sync_cdr_pending(PeriodicTask):
    """
    A periodic task that checks for pending calls to import
    """ 
    run_every = timedelta(seconds=60) # every minute

    @single_instance_task(key="sync_cdr_pending", timeout=LOCK_EXPIRE)
    def run(self, **kwargs):
    	logger = self.get_logger()
        logger.info("TASK :: sync_cdr_pending")

        if settings.LOCAL_SWITCH_TYPE=='asterisk':
            if settings.ASTERISK_IMPORT_TYPE=='mysql':
                #Import from Freeswitch Mongo
                import_cdr_asterisk_mysql()
        elif settings.LOCAL_SWITCH_TYPE=='freeswitch':
            #Import from Freeswitch Mongo
            import_cdr()

        return True


class get_channels_info(PeriodicTask):
    """
    A periodic task to retrieve channels info
    """ 
    run_every = timedelta(seconds=1) # every minute

    @single_instance_task(key="get_channels_info", timeout=60) #60 seconds
    def run(self, **kwargs):
        
        if settings.LOCAL_SWITCH_TYPE=='freeswitch':
            logger = self.get_logger()
            logger.info("TASK :: get_channels_info")

            #Get calldate
            now = datetime.datetime.today()
            date_now = datetime.datetime(now.year, now.month, now.day, now.hour, now.minute, now.second, 0)
            
            #Retrieve SwitchID
            switch_id = settings.LOCAL_SWITCH_ID
            #settings.LOCAL_SWITCH_TYPE = 'freeswitch'
            
            if settings.LOCAL_SWITCH_TYPE == 'freeswitch':
                con = False
                try:
                    con = sqlite3.connect('/usr/local/freeswitch/db/core.db')
                    cur = con.cursor()
                    cur.execute('SELECT accountcode, count(*) FROM channels')
                    rows = cur.fetchall()
                    for row in rows:
                        if not row[0]:
                            accountcode = ''
                        else:    
                            accountcode = row[0]
                        number_call = row[1] 
                        logger.debug("\n%s (accountcode:%s, switch_id:%d) ==> %s" % (date_now, accountcode, switch_id, str(number_call)))
                        
                        call_json = {
                                "switch_id" : switch_id,
                                "call_date": date_now,
                                "numbercall": number_call,
                                "accountcode": accountcode,
                                }
                        settings.DB_CONNECTION[settings.CDR_MONGO_CONC_CALL].insert(call_json)

                except sqlite3.Error, e:
                    logger.error("Error %s:" % e.args[0])
                finally:
                    if con:
                        con.close()
            elif settings.LOCAL_SWITCH_TYPE == 'asterisk':
                #TODO: Implement concurrent calls in Asterisk
                print "Asterisk needs to be implemented"

            return True