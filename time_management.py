import gi
import sys
import logging
import gc


gi.require_version('GLib', '2.0')
gi.require_version('GObject', '2.0')
gi.require_version('Gst', '1.0')


from gi.repository import Gst, GObject, GLib

logging.basicConfig(level=logging.DEBUG, format="[%(name)s] [%(levelname)8s] - %(message)s")
logger = logging.getLogger(__name__)

def TIME_ARGS(time):
    if time == Gst.CLOCK_TIME_NONE:
        return "CLOCK_TIME_NONE"
    return "%u:%02u:%02u.%09u" % (time / (Gst.SECOND * 60 * 60),
                                  (time / (Gst.SECOND * 60)) % 60,
                                  (time / Gst.SECOND) % 60,
                                  time % Gst.SECOND)

def handle_message(data, msg):
    playbin, playing, terminate, seek_enabled, seek_done, duration = data
    if msg == Gst.MessageType.ERROR:
        err, debug_info = msg.parse_error()
        logger.error(f"Error received from element {msg.src.get_name()}: {err.message}")
        logger.error(f"Debugging information: {debug_info if debug_info else 'none'}")
        terminate = True
    elif msg.type == Gst.MessageType.EOS:
        print("\nEnd of Stream reached.")
        terminate = True
    elif msg.type == Gst.MessageType.DURATION_CHANGED:
        # The duration has changed, mark the current one as invalid
        duration = Gst.CLOCK_TIME_NONE
    elif msg.type == Gst.MessageType.STATE_CHANGED:
        old_state, new_state, _ = msg.parse_state_changed()
        if type(msg.src) == type(playbin):
            print(f"Pipeline state changed from {Gst.Element.state_get_name(old_state)} to {Gst.Element.state_get_name(new_state)}. ") 
            playing = new_state == Gst.State.PLAYING

            if playing:
                start, end = 0, 0
                query = Gst.Query.new_seeking(Gst.Format.TIME)
                query.set_seeking(Gst.Format.TIME, seek_enabled, start, end)
                if playbin.query(query):
                    _, seek_enabled, start, end = query.parse_seeking()
                    if seek_enabled:
                        print(f"Seeking is ENABLED from {TIME_ARGS(start)} to {TIME_ARGS(end)}")
                    else :
                        print("Seeking is DISABLED for this stream.\n")
                else :
                    logger.error ("Seeking query failed.")
                del query
    else:
        # We should not reach here
        logger.error("Unexpected message received.\n")
    
    del msg
    gc.collect()
    return playbin, playing, terminate, seek_enabled, seek_done, duration


def main():
    # initialize GStreamer
    Gst.init(sys.argv[1:])

    playing = False                     # Are we in PLATING State ?
    terminate = False                   # Should we terminate execution ?
    seek_enabled = False                # Is seek enabled for this media ?
    seek_done = False                   # Have we performed seek already ?
    duration = Gst.CLOCK_TIME_NONE      # How long does this media last , in ns

    # create playbin ( a pipeline in itself )
    playbin = Gst.ElementFactory.make("playbin", "playbin")

    if not playbin:
        logger.error("Not all elements could be created successfully!")
        sys.exit(1)
    
    playbin.set_property("uri", "https://www.freedesktop.org/software/gstreamer-sdk/data/media/sintel_trailer-480p.webm")

    # Start playing
    ret = playbin.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        logger.error("Unable to set the pipeline to the playing state.")
        sys.exit(1)
    
    bus = playbin.get_bus()
    while not terminate:
        msg = bus.timed_pop_filtered(
            100 * Gst.MSECOND,
            Gst.MessageType.STATE_CHANGED | Gst.MessageType.ERROR | Gst.MessageType.EOS | Gst.MessageType.DURATION_CHANGED
        )

        if msg:
            playbin, playing, terminate, seek_enabled, seek_done, duration = handle_message(
                [playbin, playing, terminate, seek_enabled, seek_done, duration], msg)

        else:
            # we got no message the timeout expired
            if playing:
                current = -1

                # query the current position of the stream
                done, current = playbin.query_position(Gst.Format.TIME)
                if not done:
                    logger.error("Could not query current position.")
                
                # query stream duration
                if duration == Gst.CLOCK_TIME_NONE:
                    duration = playbin.query_duration(Gst.Format.TIME)
                    if not duration:
                        logger.error("Could not query current duration.")
                
                # print current position and total duration
                print(f"Position {TIME_ARGS(current)}/{TIME_ARGS(duration[1])}", end="\r")

                # is seeking is enabled for this stream and we havent done it yet, and the time is right, seek.
                if seek_enabled and not seek_done and current > 10 * Gst.SECOND:
                    print("\nReached 10s, performing seek...")
                    playbin.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 30 * Gst.SECOND)
                    seek_done = True
                
    del bus
    playbin.set_state(Gst.State.NULL)
    del playbin
    gc.collect()
    

if __name__=="__main__":
    main()