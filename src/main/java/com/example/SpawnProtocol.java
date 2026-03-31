package com.example;

import akka.actor.typed.*;
import akka.actor.typed.javadsl.*;
import akka.actor.typed.receptionist.*;

public class SpawnProtocol {
    public interface Serializable {}

    public static final ServiceKey<Spawn> SERVICE_KEY = ServiceKey.create(Spawn.class, "spawner-service");

    public static class Spawn implements Serializable {
        public final String name;
        public final ActorRef<ActorRef<String>> replyTo;

        public Spawn(String name, ActorRef<ActorRef<String>> replyTo) {
            this.name = name;
            this.replyTo = replyTo;
        }
    }

    public static Behavior<Spawn> create() {
        return Behaviors.setup(context -> {
            // Register so Node A can find this spawner
            context.getSystem().receptionist().tell(Receptionist.register(SERVICE_KEY, context.getSelf()));
            
            return Behaviors.receive(Spawn.class)
                .onMessage(Spawn.class, cmd -> {
                    context.getLog().info("SPAWNING actor: " + cmd.name);
                    // This is the actual 'spawn' execution
                    ActorRef<String> child = context.spawn(Worker.create(), cmd.name);
                    cmd.replyTo.tell(child);
                    return Behaviors.same();
                }).build();
        });
    }
}