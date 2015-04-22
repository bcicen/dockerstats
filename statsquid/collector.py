import json,logging
from time import sleep
from docker import Client
from redis import StrictRedis
from multiprocessing import Process 

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('statsquid')

class StatCollector(object):
    """
    Collects stats from all containers on a single Docker host, appending
    container name and id fields and publishing to redis
    params:
     - docker_host(str): full base_url of a Docker host to connect to.
                  (e.g. 'tcp://127.0.0.1:4243')
     - redis_host(str): redis host to connect to. default 127.0.0.1
     - redis_port(int): port to connect to redis host on. default 6379
    """
    def __init__(self,docker_host,redis_host='127.0.0.1',redis_port=6379):
        self.docker     = Client(base_url=docker_host)
        self.source     = self.docker.info()['Name']
        self.ncpu       = self.docker.info()['NCPU']
        self.redis      = StrictRedis(host=redis_host,port=redis_port,db=0)
        self.children   = []

        print('starting collector on source %s' % self.source)
        self.reload()

    def _collector(self,cid,cname):
        """
        Collector instance collects stats via Docker API streaming web socket,
        appending container name and source, and publishing to redis
        params:
         - cid(str): ID of container to collect stats from
         - cname(str): Name of container
        """
        sleep(5) # sleep to allow container to fully start
        log.info('starting collector for container %s' % cid)
        stats = self.docker.stats(cid)
        for stat in stats:
            #append additional information to the returned stat
            s = json.loads(stat)
            s['container_name'] = cname
            s['container_id'] = cid
            s['source'] = self.source
            s['ncpu'] = self.ncpu
            self.redis.publish("stats",json.dumps(s))
    
    def _event_listener(self):
        """
        Worker to listen for docker events and dynamically add or remove
        stat collectors based on start and die events
        """
        log.info('starting event listener')
        for event in self.docker.events():
            event = json.loads(event)
            if event['status'] == 'start':
                self._add_collector(event['id'])
            if event['status'] == 'die':
                self._remove_collector(event['id'])

    def reload(self):
        self.stop()

        for cid in [ c['Id'] for c in self.docker.containers() ]:
            self._add_collector(cid)

        #start event listener
        el = Process(target=self._event_listener,name='event_listener')
        el.start()
        self.children.append(el)

    def stop(self):
        for c in self.children:
            c.terminate()
            while c.is_alive():
                sleep(.2)
        #self.children = []

    def _add_collector(self,cid):
        log.debug('creating collector for container %s' % cid)
        cname = self.docker.inspect_container(cid)['Name'].strip('/')

        p = Process(target=self._collector,name=cid,args=(cid,cname))
        self.children.append(p)

        p.start()

    def _remove_collector(self,cid):
        c = self._get_collector(cid)
        c.terminate()
        #while c.is_alive():
        #    sleep(.2)
        log.info('collector stopped for container %s' % cid)

    def _get_collector(self,cid):
        return [ p for p in self.children if p.name == cid ][0]
