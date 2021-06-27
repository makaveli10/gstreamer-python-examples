#!/usr/bin/env python3
import sys
import gi
import logging


gi.require_version('GLib', '2.0')
gi.require_version('GObject', '2.0')
gi.require_version('Gst', '1.0')


from gi.repository import Gst, GObject, GLib

logging.basicConfig(level=logging.DEBUG, format="[%(name)s] [%(levelname)8s] - %(message)s")
logger = logging.getLogger(__name__)

# This function will be called by the pad-added signal
def pad_added_handler(src, new_pad, data):
    sink_pad = data[2].get_static_pad("sink")

    # If our converter is already linked, we have nothing to do here 
    if sink_pad.is_linked():
        print("We are already linked. Ignoring.\n")
        return

    # check the new pads type
    new_pad_caps = new_pad.get_current_caps()        # Gets the capabilities currently configured on pad.
    new_pad_struct = new_pad_caps.get_structure(0)   # Finds the structure in caps that has the index 0, and returns it. 
    new_pad_type = new_pad_struct.get_name()         # Get the name of structure as a string

    print(new_pad_type)
    if not new_pad_type.startswith("audio/x-raw"):
        print(f"It has type {new_pad_type} which is not raw audio. Ignoring.\n")
        return
    
    #  Attempt the link
    ret = new_pad.link(sink_pad)
    if ret:
        print(f"Type is {new_pad_type} but link failed {ret}.\n")
    else:
        print(f"Link succeeded (type {new_pad_type}).\n")



def main():
    # initialize GStreamer
    Gst.init(sys.argv[1:])

    # create the elements
    source = Gst.ElementFactory.make("uridecodebin", "source0")
    convert = Gst.ElementFactory.make("audioconvert", "convert")
    resample = Gst.ElementFactory.make("audioresample", "resample")
    sink = Gst.ElementFactory.make("autoaudiosink", "sink")

    # create the pipeline
    pipeline = Gst.Pipeline.new("test-pipeline")

    if not source or not convert or not resample or not sink:
        logger.error("Not all elements could be created.\n")
        sys.exit(1)

    # Build the pipeline. Note that we are NOT linking the source at this
    # point. We will do it later
    pipeline.add(source)
    pipeline.add(convert)
    pipeline.add(resample)
    pipeline.add(sink)
    
    if not convert.link(resample) or not resample.link(sink):
        logger.error("Elements could not be linked.\n")
        sys.exit(1)

    # set the Uri to play
    source.set_property("uri", "https://www.freedesktop.org/software/gstreamer-sdk/data/media/sintel_trailer-480p.webm")
    
    print("connecting pad-added signal")
    # Connect to the pad-added signal
    data = [pipeline, source, convert, resample, sink]
    source.connect("pad_added", pad_added_handler, data)

    # start playing
    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        print("Unable to set the pipeline to the playing state.\n")
        pipeline.unref()
        return

    # Listen to the bus
    bus = pipeline.get_bus()
    terminate = False

    while not terminate:
        msg = bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE, Gst.MessageType.STATE_CHANGED | Gst.MessageType.ERROR | Gst.MessageType.EOS
        )
        if msg:
            if msg.type == Gst.MessageType.ERROR:
                err, debug_info = msg.parse_error()
                logger.error(f"Error received from element {msg.src.get_name()}: {err.message}")
                logger.error(f"Debugging information: {debug_info if debug_info else 'none'}")
                terminate = True
            elif msg.type == Gst.MessageType.EOS:
                logger.info("End-Of-Stream reached.")
                terminate = True
            elif msg.type == Gst.MessageType.STATE_CHANGED:
                # We are only interested in state-changed messages from the pipeline
                if type(msg.src) == type(pipeline):
                    old_state, new_state, pending_state = msg.parse_state_changed()
                    logger.info(
                        f"Pipeline state changed from {Gst.Element.state_get_name(old_state)} to {Gst.Element.state_get_name(new_state)}:\n"
                    )
            else:
                logger.error("Unexpected message received.\n")
    
    pipeline.set_state(Gst.State.NULL)


if __name__=="__main__":
    main()


