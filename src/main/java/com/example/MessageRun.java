package com.example;

import akka.actor.typed.*;
import akka.actor.typed.javadsl.*;
import akka.actor.typed.receptionist.*;
import com.typesafe.config.*;
import java.time.Duration;
import java.util.Set;

public class MessageRun {

    // 1. MESSAGES
    public interface MessageSerializable {}

    public static class Ping implements MessageSerializable {
        // Must be public and non-final for Jackson default deserialization
        public ActorRef<Pong> replyTo;

        // Jackson needs this empty constructor!
        public Ping() {} 

        public Ping(ActorRef<Pong> replyTo) {
            this.replyTo = replyTo;
        }
    }

    // Empty classes already have a default constructor, so these are fine
    public static class Pong implements MessageSerializable {}
    public static class Start implements MessageSerializable {}

    public static final ServiceKey<Ping> PONGER_KEY = ServiceKey.create(Ping.class, "ponger-key");

    // 2. THE PONGER (Node B)
    public static Behavior<Ping> pongerBehavior() {
        return Behaviors.setup(context -> {
            context.getSystem().receptionist().tell(Receptionist.register(PONGER_KEY, context.getSelf()));
            return Behaviors.receive(Ping.class)
                .onMessage(Ping.class, msg -> {
                    // msg.replyTo is now correctly populated by Jackson
                    msg.replyTo.tell(new Pong());
                    return Behaviors.same();
                }).build();
        });
    }

    // 3. THE PINGER (Node A Logic)
    public static Behavior<Object> pingerBehavior(ActorRef<Ping> target, int limit) {
        return Behaviors.setup(context -> new PingerHandler(context, target, limit));
    }

    private static class PingerHandler extends AbstractBehavior<Object> {
        private final ActorRef<Ping> target;
        private final int limit;
        private int count = 0;
        private long startTime = 0;

        public PingerHandler(ActorContext<Object> context, ActorRef<Ping> target, int limit) {
            super(context);
            this.target = target;
            this.limit = limit;
        }

        @Override
        public Receive<Object> createReceive() {
            return newReceiveBuilder()
                .onMessage(Start.class, s -> {
                    System.out.println("LOG_START:" + System.currentTimeMillis());
                    startTime = System.currentTimeMillis();
                    target.tell(new Ping(getContext().getSelf().narrow()));
                    return this;
                })
                .onMessage(Pong.class, p -> {
                    count++;
                    if (count < limit) {
                        target.tell(new Ping(getContext().getSelf().narrow()));
                        return this;
                    } else {
                        long end = System.currentTimeMillis();
                        System.out.println("LOG_END:" + end);
                        System.out.println("--- FINISHED ---");
                        System.out.println("Time taken: " + (end - startTime) + " ms");
                        return Behaviors.stopped();
                    }
                })
                .build();
        }
    }

    // 4. THE DISCOVERY LOGIC
    public static Behavior<Receptionist.Listing> createDiscovery(int limit) {
        return Behaviors.setup(context -> {
            context.getSystem().receptionist().tell(Receptionist.subscribe(PONGER_KEY, context.getSelf()));

            return Behaviors.receive(Receptionist.Listing.class)
                .onMessage(Receptionist.Listing.class, listing -> {
                    Set<ActorRef<Ping>> instances = listing.getServiceInstances(PONGER_KEY);
                    if (!instances.isEmpty()) {
                        ActorRef<Ping> ponger = instances.iterator().next();
                        context.getLog().info("Node A: Found Node B! Starting Pinger...");
                        
                        ActorRef<Object> pinger = context.spawn(pingerBehavior(ponger, limit), "pinger");
                        pinger.tell(new Start());
                    }
                    return Behaviors.same();
                }).build();
        });
    }

    public static void main(String[] args) {
        if (args.length < 3) {
            System.out.println("Usage: MessageRun <port> <localIp> <seedIp>");
            System.exit(1);
        }

        String port = args[0];
        String localIp = args[1];
        String seedIp = args[2];
        int messageLimit = 1000000; 

        String configString = 
            "akka.actor.provider = cluster\n" +
            "akka.remote.artery.canonical.port = " + port + "\n" +
            "akka.remote.artery.canonical.hostname = \"" + localIp + "\"\n" +
            "akka.cluster.seed-nodes = [\"akka://MessageSystem@" + seedIp + ":2551\"]\n" +
            "akka.actor.serialization-bindings {\n" +
            "  \"com.example.MessageRun$MessageSerializable\" = jackson-cbor\n" +
            "}";

        Config config = ConfigFactory.parseString(configString).withFallback(ConfigFactory.load());

        if (port.equals("2551")) {
            ActorSystem.create(pongerBehavior(), "MessageSystem", config);
            System.out.println("Node B (Ponger) is UP on " + localIp + ":2551");
        } else {
            ActorSystem.create(createDiscovery(messageLimit), "MessageSystem", config);
            System.out.println("Node A (Pinger) is UP on " + localIp + ":" + port);
        }
    }
}