import logging
import ast

import paho.mqtt.client as mqtt
import configparser

from c8ydm.framework.modulebase import Sensor, Initializer, Listener
from c8ydm.framework.smartrest import SmartRESTMessage


class SchindlerDeviceSensor(Sensor, Initializer, Listener):


    BIT_MASKS = {
        'CN_ACC_FLAG'  : 0x0001,
        'DR_ACC1_FLAG' : 0x0002,
        'DR_ACC2_FLAG' : 0x0004,
        'DR_ACC3_FLAG' : 0x0008,
        'DR_ACC4_FLAG' : 0x0010,
        'TE_BARO_FLAG' : 0x0020,
        'ST_BARO_FLAG' : 0x0040,
        'HUM_FLAG'     : 0x0080,
        'MOT_FLAG'     : 0x0100,
        'MAG_FLAG'     : 0x0200,
        'BCS_FLAG'     : 0x0400
    }

    logger = logging.getLogger(__name__)
    fragment = 'c8y_Message'
    message_id = 'dm502'
    xid = 'c8y-dm-agent-v1.0'
    client = None

    data_buffer = []

    def _set_executing(self):
        executing = SmartRESTMessage('s/us', '501', [self.fragment])
        self.agent.publishMessage(executing)

    def _set_success(self):
        success = SmartRESTMessage('s/us', '503', [self.fragment])
        self.agent.publishMessage(success)

    def _set_failed(self, reason):
        failed = SmartRESTMessage('s/us', '502', [self.fragment, reason])
        self.agent.publishMessage(failed)

    def handleOperation(self, message):
        """Callback that is executed for any operation received

            Raises:
            Exception: Error when handling the operation
       """
        try:
            # self.logger.debug(
            #    f'Handling Cloud Remote Access operation: listener={__name__}, message={message}')

            if message.messageId == self.message_id:
                self._set_executing()
                message = message.values[1]
                self.display_message(message)
                self._set_success()

        except Exception as ex:
            self.logger.error(f'Handling operation error. exception={ex}')
            self._set_failed(str(ex))
            # raise

    def getSensorMessages(self):
        try:
            response = self.data_buffer.copy()
            self.data_buffer.clear()
            return response
        except Exception as e:
            self.logger.exception(
                f'Error in Schindler MQTT bridge getSensorMessages: {e}', e)

    def getMessages(self):

        asdm_config = configparser.ConfigParser(delimiters=',')
        asdm_config.read_file(open("/opt/asdm.config"))
        TOPIC_ROOT = "data/" + asdm_config.get('ASDM', 'CountryCode') + "/" + asdm_config.get('ASDM', 'EquipmentNr')
        self.TOPIC_FLOOR         = TOPIC_ROOT + "/sensor/SN10_02"
        self.TOPIC_SENSOR_FLAGS  = TOPIC_ROOT + "/sensor/SN20_01"

        try:
            self.logger.info('Starting mqtt connection ...')
            self.client = mqtt.Client('c8y_agent_client')
            self.client.on_connect = self.on_mqtt_connect
            self.client.on_message = self.on_mqtt_message
            self.client.connect('localhost')
            self.client.loop_start()
            self.logger.info('mqtt connection established')

            return self.data_buffer
        except Exception as e:
            self.logger.exception(f'Error in Schindler MQTT bridge getMessages: {e}', e)

    def display_message(self, message):
        pass

    def getSupportedOperations(self):
        return [self.fragment]

    def getSupportedTemplates(self):
        return [self.xid]

    def on_mqtt_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        self.client.subscribe(self.TOPIC_FLOOR)
        self.client.subscribe(self.TOPIC_SENSOR_FLAGS)

    def on_mqtt_message(self, client, userdata, msg):
        print(msg.topic+" "+str(msg.payload))
        dict_str = msg.payload.decode("UTF-8")
        mydata = ast.literal_eval(dict_str)    
        if msg.topic == self.TOPIC_SENSOR_FLAGS:
            byte = mydata["0"]
            for bitMaskName in self.BIT_MASKS.keys():
                value = self.BIT_MASKS[bitMaskName] & byte
                self.data_buffer.append(SmartRESTMessage('s/us', '200', ['ASDM', bitMaskName, value]))
        
        elif msg.topic == self.TOPIC_FLOOR:
            floor_level = mydata["0"]
            self.data_buffer.append(SmartRESTMessage('s/us', '200', ['ASDM', 'floor_level', floor_level]))
