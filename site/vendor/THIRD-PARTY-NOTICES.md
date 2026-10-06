# Vendored browser dependencies

- Swiper 14.3.0: https://swiperjs.com/ and https://github.com/nolimits4web/swiper. MIT; license included in swiper/LICENSE.
- MediaPipe Tasks Vision 0.10.32: https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector/web_js. Apache 2.0; license included in vision/LICENSE. vision_bundle.js is the unmodified published CommonJS bundle, exposed through exports in a classic browser worker so its WASM loader can use importScripts. The original module bundle is retained as distributed.
- BlazeFace short-range float16 detector: https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite. Official MediaPipe model distributed under Apache 2.0: https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector.

Files are served locally; no added CDN dependency. Face detection identifies boxes, not a person's identity. Users confirm names and may correct labels.
