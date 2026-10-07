Optional Umcimby marketing demo image

Add a JPG at this exact path:

    app/static/images/demo/demo-event.jpg

Then run:

    flask --app run seed-demo

The seed command copies the image into Umcimby's private event-photo storage and attaches it to the demo event. The demo still works without the image and will use the existing event-photo placeholder.
