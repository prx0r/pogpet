// Classic worker: MediaPipe's WASM loader uses importScripts.
self.exports = {};
importScripts('../vendor/vision/vision_bundle.js');
const {FaceDetector, FilesetResolver} = self.exports;
delete self.exports;
let detector;
self.onmessage = async function (e) {
  const {id, bitmap} = e.data;
  try {
    if (!detector) {
      const files = await FilesetResolver.forVisionTasks('/vendor/vision/wasm');
      detector = await FaceDetector.createFromOptions(files, {
        baseOptions: {modelAssetPath:'/vendor/vision/face-detector.tflite',delegate:'CPU'},
        runningMode:'IMAGE',minDetectionConfidence:0.55
      });
    }
    const result=detector.detect(bitmap);
    const faces=result.detections.map(function(d){
      const b=d.boundingBox;
      const x=Math.max(0,b.originX/bitmap.width),y=Math.max(0,b.originY/bitmap.height);
      return {box:[x,y,Math.min(1-x,b.width/bitmap.width),Math.min(1-y,b.height/bitmap.height)]};
    });
    self.postMessage({id,faces});
  } catch(error) {self.postMessage({id,error:error.message});}
  finally {bitmap.close();}
};
