import json
import numpy as np
from google.protobuf import json_format
import base64
import tensorflow as tf
from tensorflow.core.framework.tensor_pb2 import TensorProto
from PIL import Image
import io

from seldon_core.wrapper import get_rest_microservice, SeldonModelGRPC, get_grpc_server
from seldon_core.proto import prediction_pb2
from seldon_core.user_model import SeldonComponent
from seldon_core.utils import (seldon_message_to_json,json_to_seldon_message)

from flask import jsonify

"""
 Checksum of bytes. Used to check data integrity of binData passed in multipart/form-data request

 Parameters
 ----------
  the_bytes
    Input bytes

  Returns
  -------
  the checksum
"""
def rs232_checksum(the_bytes):
    return b'%02X' % (sum(the_bytes) & 0xFF)

class UserObject(SeldonComponent):
    def __init__(self, metrics_ok=True, ret_nparray=False, ret_meta=False):
        self.metrics_ok = metrics_ok
        self.ret_nparray = ret_nparray
        self.nparray = np.array([1, 2, 3])
        self.ret_meta = ret_meta

    def predict(self, X, features_names, **kwargs):
        """
        Return a prediction.

        Parameters
        ----------
        X : array-like
        feature_names : array of feature names (optional)
        """
        if self.ret_meta:
            self.inc_meta = kwargs.get("meta")
        if self.ret_nparray:
            return self.nparray
        else:
            print("Predict called - will run identity function")
            print(X)
            return X

    def feedback(self, features, feature_names, reward, truth):
        print("Feedback called")

    def tags(self):
        if self.ret_meta:
            return {"inc_meta": self.inc_meta}
        else:
            return {"mytag": 1}

    def metrics(self):
        if self.metrics_ok:
            return [{"type": "COUNTER", "key": "mycounter", "value": 1}]
        else:
            return [{"type": "BAD", "key": "mycounter", "value": 1}]


class UserObjectLowLevel(SeldonComponent):
    def __init__(self, metrics_ok=True, ret_nparray=False):
        self.metrics_ok = metrics_ok
        self.ret_nparray = ret_nparray
        self.nparray = np.array([1, 2, 3])

    def predict_rest(self, request):
        return {"data": {"ndarray": [9, 9]}}

    def predict_grpc(self, request):
        arr = np.array([9, 9])
        datadef = prediction_pb2.DefaultData(
            tensor=prediction_pb2.Tensor(
                shape=(2, 1),
                values=arr
            )
        )
        request = prediction_pb2.SeldonMessage(data=datadef)
        return request

    def send_feedback_rest(self, request):
        print("Feedback called")

    def send_feedback_grpc(self, request):
        print("Feedback called")


class UserObjectLowLevelWithPredictRaw(SeldonComponent):
    def __init__(self, check_name):
        self.check_name=check_name
    def predict_raw(self, msg):
        msg=json_to_seldon_message(msg)
        if self.check_name == 'img':
            file_data=msg.binData
            img = Image.open(io.BytesIO (file_data))
            img.verify()
            return {"meta": seldon_message_to_json(msg.meta),"data": {"ndarray": [rs232_checksum(file_data).decode('utf-8')]}}
        elif self.check_name == 'txt':
            file_data=msg.binData
            return {"meta": seldon_message_to_json(msg.meta),"data": {"ndarray": [file_data.decode('utf-8')]}}
        elif self.check_name == 'strData':
            file_data=msg.strData
            return {"meta": seldon_message_to_json(msg.meta), "data": {"ndarray": [file_data]}}
        

class UserObjectLowLevelGrpc(SeldonComponent):
    def __init__(self, metrics_ok=True, ret_nparray=False):
        self.metrics_ok = metrics_ok
        self.ret_nparray = ret_nparray
        self.nparray = np.array([1, 2, 3])

    def predict_grpc(self, request):
        arr = np.array([9, 9])
        datadef = prediction_pb2.DefaultData(
            tensor=prediction_pb2.Tensor(
                shape=(2, 1),
                values=arr
            )
        )
        request = prediction_pb2.SeldonMessage(data=datadef)
        return request

    def send_feedback_rest(self, request):
        print("Feedback called")

    def send_feedback_grpc(self, request):
        print("Feedback called")


def test_model_ok():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/predict?json={"data":{"names":["a","b"],"ndarray":[[1,2]]}}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]
    assert j["data"]["names"] == ["t:0", "t:1"]
    assert j["data"]["ndarray"] == [[1.0, 2.0]]

def test_model_puid_ok():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/predict?json={"meta":{"puid":"123"},"data":{"names":["a","b"],"ndarray":[[1,2]]}}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]
    assert j["data"]["names"] == ["t:0", "t:1"]
    assert j["data"]["ndarray"] == [[1.0, 2.0]]
    assert j["meta"]["puid"] == '123'

def test_model_lowlevel_ok():
    user_object = UserObjectLowLevel()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/predict?json={"data":{"ndarray":[1,2]}}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["data"]["ndarray"] == [9, 9]

def test_model_lowlevel_multi_form_data_text_file_ok():
    user_object = UserObjectLowLevelWithPredictRaw('txt')
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.post('/predict',data={"meta":'{"puid":"1234"}',"binData":(f'./tests/resources/test.txt','test.txt')},content_type='multipart/form-data')
    j = json.loads(rv.data)
    assert rv.status_code == 200
    assert j["meta"]["puid"] == "1234"
    assert j["data"]["ndarray"][0] == "this is test file for testing multipart/form-data input\n"

def test_model_lowlevel_multi_form_data_img_file_ok():
    user_object = UserObjectLowLevelWithPredictRaw('img')
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.post('/predict',data={"meta":'{"puid":"1234"}',"binData":(f'./tests/resources/test.png','test.png')},content_type='multipart/form-data')
    j = json.loads(rv.data)
    assert rv.status_code == 200
    assert j["meta"]["puid"] == "1234"
    with open('./tests/resources/test.png',"rb") as f:
        img_data=f.read()
    assert j["data"]["ndarray"][0] == rs232_checksum(img_data).decode('utf-8')

def test_model_lowlevel_multi_form_data_strData_ok():
    user_object = UserObjectLowLevelWithPredictRaw('strData')
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.post('/predict',data={"meta":'{"puid":"1234"}',"strData":(f'./tests/resources/test.txt','test.txt')},content_type='multipart/form-data')
    j = json.loads(rv.data)
    assert rv.status_code == 200
    assert j["meta"]["puid"] == "1234"
    assert j["data"]["ndarray"][0] == "this is test file for testing multipart/form-data input\n"

def test_model_multi_form_data_ok():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.post('/predict',data={"data":'{"names":["a","b"],"ndarray":[[1,2]]}'},content_type='multipart/form-data')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]
    assert j["data"]["names"] == ["t:0", "t:1"]
    assert j["data"]["ndarray"] == [[1.0, 2.0]]

def test_model_feedback_ok():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/send-feedback?json={"request":{"data":{"ndarray":[]}},"reward":1.0}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200


def test_model_feedback_lowlevel_ok():
    user_object = UserObjectLowLevel()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/send-feedback?json={"request":{"data":{"ndarray":[]}},"reward":1.0}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200


def test_model_tftensor_ok():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    arr = np.array([1, 2])
    datadef = prediction_pb2.DefaultData(
        tftensor=tf.make_tensor_proto(arr)
    )
    request = prediction_pb2.SeldonMessage(data=datadef)
    jStr = json_format.MessageToJson(request)
    rv = client.get('/predict?json=' + jStr)
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]
    assert 'tftensor' in j['data']
    tfp = TensorProto()
    json_format.ParseDict(j['data'].get("tftensor"),
                          tfp, ignore_unknown_fields=False)
    arr2 = tf.make_ndarray(tfp)
    assert np.array_equal(arr, arr2)


def test_model_ok_with_names():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get(
        '/predict?json={"data":{"names":["a","b"],"ndarray":[[1,2]]}}')
    j = json.loads(rv.data)
    assert rv.status_code == 200
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]


def test_model_bin_data():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    bdata = b"123"
    bdata_base64 = base64.b64encode(bdata).decode('utf-8')
    rv = client.get('/predict?json={"binData":"' + bdata_base64 + '"}')
    j = json.loads(rv.data)
    return_data = \
            base64.b64encode(base64.b64encode(bdata)).decode('utf-8')
    assert rv.status_code == 200
    assert j["binData"] == return_data
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]


def test_model_bin_data_nparray():
    user_object = UserObject(ret_nparray=True)
    app = get_rest_microservice(user_object)
    client = app.test_client()
    encoded = base64.b64encode(b"1234")
    rv = client.get('/predict?json={"binData":"' + str(encoded) + '"}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["data"]["tensor"]["values"] == [1, 2, 3]
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]


def test_model_str_data():
    user_object = UserObject(ret_nparray=True)
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/predict?json={"strData":"my data"}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["data"]["tensor"]["values"] == [1, 2, 3]
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]


def test_model_str_data_identity():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/predict?json={"strData":"my data"}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["strData"] == "my data"
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]


def test_model_no_json():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    uo = UserObject()
    rv = client.get('/predict?')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 400


def test_model_bad_metrics():
    user_object = UserObject(metrics_ok=False)
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/predict?json={"data":{"ndarray":[]}}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 400


def test_model_gets_meta():
    user_object = UserObject(ret_meta=True)
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get('/predict?json={"meta":{"puid": "abc"},"data":{"ndarray":[]}}')
    j = json.loads(rv.data)
    print(j)
    assert rv.status_code == 200
    assert j["meta"]["tags"] == {"inc_meta": {"puid": "abc"}}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]

def test_model_seldon_json_ok():
    user_object = UserObject()
    app = get_rest_microservice(user_object)
    client = app.test_client()
    rv = client.get("/seldon.json")
    assert rv.status_code == 200

def test_proto_ok():
    user_object = UserObject()
    app = SeldonModelGRPC(user_object)
    arr = np.array([1, 2])
    datadef = prediction_pb2.DefaultData(
        tensor=prediction_pb2.Tensor(
            shape=(2, 1),
            values=arr
        )
    )
    request = prediction_pb2.SeldonMessage(data=datadef)
    resp = app.Predict(request, None)
    jStr = json_format.MessageToJson(resp)
    j = json.loads(jStr)
    print(j)
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]
    assert j["data"]["tensor"]["shape"] == [2, 1]
    assert j["data"]["tensor"]["values"] == [1, 2]


def test_proto_lowlevel():
    user_object = UserObjectLowLevelGrpc()
    app = SeldonModelGRPC(user_object)
    arr = np.array([1, 2])
    datadef = prediction_pb2.DefaultData(
        tensor=prediction_pb2.Tensor(
            shape=(2, 1),
            values=arr
        )
    )
    request = prediction_pb2.SeldonMessage(data=datadef)
    resp = app.Predict(request, None)
    jStr = json_format.MessageToJson(resp)
    j = json.loads(jStr)
    print(j)
    assert j["data"]["tensor"]["shape"] == [2, 1]
    assert j["data"]["tensor"]["values"] == [9, 9]


def test_proto_feedback():
    user_object = UserObject()
    app = SeldonModelGRPC(user_object)
    arr = np.array([1, 2])
    datadef = prediction_pb2.DefaultData(
        tensor=prediction_pb2.Tensor(
            shape=(2, 1),
            values=arr
        )
    )
    request = prediction_pb2.SeldonMessage(data=datadef)
    feedback = prediction_pb2.Feedback(request=request, reward=1.0)
    resp = app.SendFeedback(feedback, None)


def test_proto_feedback_custom():
    user_object = UserObjectLowLevel()
    app = SeldonModelGRPC(user_object)
    arr = np.array([1, 2])
    datadef = prediction_pb2.DefaultData(
        tensor=prediction_pb2.Tensor(
            shape=(2, 1),
            values=arr
        )
    )
    request = prediction_pb2.SeldonMessage(data=datadef)
    feedback = prediction_pb2.Feedback(request=request, reward=1.0)
    resp = app.SendFeedback(feedback, None)


def test_proto_tftensor_ok():
    user_object = UserObject()
    app = SeldonModelGRPC(user_object)
    arr = np.array([1, 2])
    datadef = prediction_pb2.DefaultData(
        tftensor=tf.make_tensor_proto(arr)
    )
    request = prediction_pb2.SeldonMessage(data=datadef)
    resp = app.Predict(request, None)
    jStr = json_format.MessageToJson(resp)
    j = json.loads(jStr)
    print(j)
    assert j["meta"]["tags"] == {"mytag": 1}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]
    arr2 = tf.make_ndarray(resp.data.tftensor)
    assert np.array_equal(arr, arr2)


def test_proto_bin_data():
    user_object = UserObject()
    app = SeldonModelGRPC(user_object)
    bdata = b"123"
    bdata_base64 = base64.b64encode(bdata)
    request = prediction_pb2.SeldonMessage(binData=bdata_base64)
    resp = app.Predict(request, None)
    assert resp.binData == bdata_base64


def test_proto_bin_data_nparray():
    user_object = UserObject(ret_nparray=True)
    app = SeldonModelGRPC(user_object)
    binData = b"\0\1"
    request = prediction_pb2.SeldonMessage(binData=binData)
    resp = app.Predict(request, None)
    jStr = json_format.MessageToJson(resp)
    j = json.loads(jStr)
    print(j)
    assert j["data"]["tensor"]["values"] == list(user_object.nparray.flatten())


def test_get_grpc_server():
    user_object = UserObject(ret_nparray=True)
    server = get_grpc_server(user_object)


def test_proto_gets_meta():
    user_object = UserObject(ret_meta=True)
    app = SeldonModelGRPC(user_object)
    arr = np.array([1, 2])
    datadef = prediction_pb2.DefaultData(
        tensor=prediction_pb2.Tensor(
            shape=(2, 1),
            values=arr
        )
    )
    meta = prediction_pb2.Meta()
    metaJson = {"puid": "abc"}
    json_format.ParseDict(metaJson, meta)
    request = prediction_pb2.SeldonMessage(data=datadef, meta=meta)
    resp = app.Predict(request, None)
    jStr = json_format.MessageToJson(resp)
    j = json.loads(jStr)
    print(j)
    assert j["meta"]["tags"] == {"inc_meta": {"puid": "abc"}}
    assert j["meta"]["metrics"][0]["key"] == user_object.metrics()[0]["key"]
    assert j["meta"]["metrics"][0]["value"] == user_object.metrics()[0]["value"]
    assert j["data"]["tensor"]["shape"] == [2, 1]
    assert j["data"]["tensor"]["values"] == [1, 2]
