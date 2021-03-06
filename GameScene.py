from ParticlePlay import Scene
from ParticlePlay import Color
from Network import *
from Bonus import *
from Bullet import *
from Player import *
import math


class GameScene(Scene):
    player = None
    bullets = {}
    bonuses = {}
    players = {}
    show_info = False

    def __init__(self, username, clientSocket):
        self.username = username
        self.clientSocket = clientSocket
        self.clientSocket.setListener(self.listener)

    def playerDelegate(self, player, key):
        if key == "HealthBar":
            return self.show_info
        return True

    def listener(self, packet):
        self.clientSocket.clientLock()
        if isinstance(packet, Packets.RequestGameStatePacket):
            w, h = self.getGame().getSize()
            self.player = Player(
                self.getGame(), [w/2, h/2], Color(255, 255, 255)
            )
            self.player.setPlayerName(self.username)
            self.bullets = {}
            self.bonuses = {}
            self.players = {}
        elif isinstance(packet, Packets.PlayerInfoPacket):
            if packet.isMe():
                self.player.setHealth(packet.getHealth())
                self.player.setDeath(packet.getDeath())
                self.player.setRespawnTime(packet.getRespawnTime())
            else:
                if packet.getPlayerId() not in self.players:
                    player = Player(self.getGame())
                    player.setPlayerName(packet.getPlayerName())
                    self.players[packet.getPlayerId()] = player
                else:
                    player = self.players[packet.getPlayerId()]
                player.setDelegate(lambda p, k: self.playerDelegate(p, k))
                player.setPosition(packet.getPosition())
                player.setVelocity(packet.getVelocity())
                player.setAngle(packet.getAngle())
                player.setHealth(packet.getHealth())
                player.setDeath(packet.getDeath())
                player.resetTimeout()
        elif isinstance(packet, Packets.BulletInfoPacket):
            if packet.getBulletId() not in self.bullets:
                bullet = Bullet()
                self.bullets[packet.getBulletId()] = bullet
            else:
                bullet = self.bullets[packet.getBulletId()]
            bullet.setPosition(packet.getPosition())
            bullet.setVelocity(packet.getVelocity())
            bullet.resetTimeout()
            if not packet.isAlive():
                bullet.kill()
        elif isinstance(packet, Packets.BonusInfoPacket):
            if packet.getBonusId() not in self.bonuses:
                bonus = Bonus()
                self.bonuses[packet.getBonusId()] = bonus
            else:
                bonus = self.bonuses[packet.getBonusId()]
            bonus.setPosition(packet.getPosition())
            bonus.resetTimeout()
            if not packet.isAlive():
                bonus.kill()
        elif isinstance(packet, Packets.PlayerGunPacket):
            self.player.getGun().setReload(packet.isReloading())
            self.player.getGun().setBulletInMagazine(
                packet.getBulletInMagazine()
            )
            self.player.getGun().setTotalBullet(packet.getTotalBullet())
        elif packet is not None:
            print("Packet received (type " + str(packet) + ")")
        self.clientSocket.clientUnlock()

    def onInit(self):
        w, h = self.getGame().getSize()
        self.player = Player(self.getGame(), [w/2, h/2], Color(255, 255, 255))
        self.player.setPlayerName(self.username)

    def onRender(self, renderer, delta):
        px, py = self.player.getPosition()
        renderer.drawString(
            (10, 20), "Player Position: " + str(px) + ", " + str(py)
        )
        renderer.drawString(
            (10, 35), "Bullets on screen: " + str(len(self.bullets))
        )
        renderer.drawString(
            (10, self.getGame().getSize()[1]-20),
            "Health: " + str(self.player.getHealth())
        )
        if self.show_info:
            offset = 0
            for player in [self.player] + list(self.players.values()):
                import Tkinter as tk
                renderer.drawString(
                    (self.getGame().getWidth() - 10, 5 + offset),
                    "%s%s: %s Deaths" % (
                        "> "
                        if player.getPlayerName() == self.player.getPlayerName()
                        else "",
                        player.getPlayerName(), player.getDeath()
                    ),
                    anchor=tk.NE
                )
                if player.getPlayerName() != self.player.getPlayerName():
                    renderer.drawString(
                        player.getPosition(),
                        player.getPlayerName(),
                        anchor=tk.CENTER
                    )
                offset += 12
        if self.player.getGun().isReloading():
            renderer.drawString(
                (
                    self.getGame().getSize()[0]-75,
                    self.getGame().getSize()[1]-20
                ),
                "Reloading"
            )
        else:
            renderer.drawString(
                (
                    self.getGame().getSize()[0]-50,
                    self.getGame().getSize()[1]-20
                ), (
                    str(self.player.getGun().getBulletInMagazine()) +
                    "/" + str(self.player.getGun().getTotalBullet())
                )
            )

        self.clientSocket.clientLock()
        for bid in self.bullets:
            bullet = self.bullets[bid]
            bullet.onRender(renderer)
        for bid in self.bonuses:
            bonus = self.bonuses[bid]
            bonus.onRender(renderer)
        for pid in self.players:
            player = self.players[pid]
            player.onRender(renderer)
        self.clientSocket.clientUnlock()

        self.player.onRender(renderer)
        if self.player.getRespawnTime() > 0:
            import Tkinter as tk
            renderer.drawString(
                [px, py], "%.2fs" % (self.player.getRespawnTime()),
                anchor=tk.CENTER
            )

    def onUpdate(self, gameInput, delta):
        self.clientSocket.clientLock()
        vx = 0
        vy = 0
        if gameInput.isKeyDown("d"):
            vx += self.player.getSpeed()
        elif gameInput.isKeyDown("a"):
            vx -= self.player.getSpeed()
        if gameInput.isKeyDown("s"):
            vy += self.player.getSpeed()
        elif gameInput.isKeyDown("w"):
            vy -= self.player.getSpeed()
        self.show_info = gameInput.isKeyDown("space")
        self.player.setVelocity([vx, vy])
        self.player.onUpdate(delta)
        self.clientSocket.sendPacket(PlayerInfoPacket(
            self.player.getPlayerName(),
            self.player.getPosition(), self.player.getVelocity(),
            self.player.getAngle(), self.player.getHealth()
        ))

        px, py = self.player.getPosition()
        x, y = gameInput.getMousePosition()
        angle = math.atan2(x-px, y-py)
        self.player.setAngle(angle)
        self.player.resetTimeout()
        if gameInput.isMouseDown(cooldown=5):
            self.clientSocket.sendPacket(PlayerGunPacket())

        new_bullets = {}
        for bid in self.bullets:
            bullet = self.bullets[bid]
            bullet.onUpdate(delta)
            w, h = self.getGame().getSize()
            x, y = bullet.getPosition()
            if (x < -(bullet.getSize()/2) or x > w+(bullet.getSize()/2) or
                    y < -(bullet.getSize()/2) or y > h+(bullet.getSize()/2)):
                bullet.kill()

            for clientid in self.players:
                player = self.players[clientid]
                if player.isIntersectObject(bullet):
                    bullet.kill()
            if bullet.isAlive() and not bullet.isTimeout():
                new_bullets[bid] = bullet
        self.bullets = new_bullets

        new_bonuses = {}
        for bid in self.bonuses:
            bonus = self.bonuses[bid]
            bonus.onUpdate(delta)

            for clientid in self.players:
                player = self.players[clientid]
                if player.isIntersectObject(bonus):
                    bonus.kill()
            if bonus.isAlive() and not bonus.isTimeout():
                new_bonuses[bid] = bonus
        self.bonuses = new_bonuses

        new_players = {}
        for pid in self.players:
            player = self.players[pid]
            if not player.isDead():
                new_players[pid] = player
        self.players = new_players

        if self.player.isDead():
            w, h = self.getGame().getSize()
            self.player.respawn([w/2, h/2])
        if not self.clientSocket.isServerAlive():
            from ServerConnectScene import ServerConnectScene
            self.getGame().enterScene(
                ServerConnectScene(
                    self.username,
                    self.clientSocket.host,
                    self.clientSocket.port,
                    "Server timeout"
                )
            )
        self.clientSocket.clientUnlock()
        if gameInput.isKeyDown("escape"):
            self.getGame().stopGame()

    def onExit(self):
        self.clientSocket.closeSocket()
        import time
        disconnectTimeout = time.time()
        while (self.clientSocket.isConnected() and
                disconnectTimeout+3.0 > time.time()):
            continue
