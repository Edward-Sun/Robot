import pyglet

def exit_callback(dt):
    pyglet.app.exit()

music = pyglet.resource.media('auido.mp3', streaming=False)
music.play()

pyglet.clock.schedule_once(exit_callback , music.duration)
pyglet.app.run()