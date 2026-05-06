package com.example;

import akka.actor.typed.*;
import akka.actor.typed.javadsl.*;
import akka.actor.typed.receptionist.*;
import com.typesafe.config.*;
import java.util.Set;

public class MessageRun {
    public interface MessageSerializable {}

    // 1. MESSAGES (Fixed for Jackson)
    public static class Ping implements MessageSerializable {
        public ActorRef<Pong> replyTo;
        public Ping() {} 
        public Ping(ActorRef<Pong> replyTo) { this.replyTo = replyTo; }
    }

    public static class Pong implements MessageSerializable { public Pong() {} }
    public static class Start implements MessageSerializable { public Start() {} }

    public static final ServiceKey<Ping> PONGER_KEY = ServiceKey.create(Ping.class, "ponger-key");

    // 2. THE PONGER (Node B / Seed)
    public static Behavior<Ping> pongerBehavior() {
        return Behaviors.setup(context -> {
            context.getSystem().receptionist().tell(Receptionist.register(PONGER_KEY, context.getSelf()));
            return Behaviors.receive(Ping.class)
                .onMessage(Ping.class, msg -> {
                    msg.replyTo.tell(new Pong());
                    return Behaviors.same();
                }).build();
        });
    }

    // 3. THE PINGER (Node A / Master)
    public static class Pinger extends AbstractBehavior<Object> {
        private final ActorRef<Ping> target;
        private final int limit;
        private int count = 0;
        private long startTime;

        public Pinger(ActorContext<Object> context, ActorRef<Ping> target, int limit) {
            super(context);
            this.target = target;
            this.limit = limit;
            // Kick off the first ping immediately
            System.out.println("LOG_START:" + System.currentTimeMillis());
            this.startTime = System.currentTimeMillis();
            sendPing();
        }

        private void sendPing() {
            target.tell(new Ping(getContext().getSelf().narrow()));
        }

        @Override
        public Receive<Object> createReceive() {
            return newReceiveBuilder()
                .onMessage(Pong.class, msg -> {
                    count++;
                    if (count < limit) {
                        sendPing();
                    } else {
                        System.out.println("LOG_END:" + System.currentTimeMillis());
                        System.out.println("Time: " + (System.currentTimeMillis() - startTime) + "ms");
                        getContext().getSystem().terminate();
                    }
                    return this;
                }).build();
        }
    }

    // 4. MAIN
    public static void main(String[] args) {
        if (args.length < 3) { System.exit(1); }
        String port = args[0];
        String localIp = args[1];
        String seedIp = args[2];
        int messageLimit = 10000; // Match Elixir

        Config config = ConfigFactory.parseString(
            "akka.actor.provider = cluster\n" +
            "akka.remote.artery.canonical.port = " + port + "\n" +
            "akka.remote.artery.canonical.hostname = \"" + localIp + "\"\n" +
            "akka.cluster.seed-nodes = [\"akka://MessageSystem@" + seedIp + ":2551\"]\n" +
            "akka.actor.serialization-bindings { \"com.example.MessageRun$MessageSerializable\" = jackson-cbor }"
        );

        if (port.equals("2551")) {
            ActorSystem.create(pongerBehavior(), "MessageSystem", config);
        } else {
            ActorSystem.create(Behaviors.setup(context -> {
                context.getSystem().receptionist().tell(Receptionist.subscribe(PONGER_KEY, context.getSelf().narrow()));
                return Behaviors.receive(Object.class).onMessage(Receptionist.Listing.class, list -> {
                    Set<ActorRef<Ping>> instances = list.getServiceInstances(PONGER_KEY);
                    if (!instances.isEmpty()) {
                        // Start the Pinger loop
                        context.spawn(Behaviors.setup(ctx -> new Pinger(ctx, instances.iterator().next(), messageLimit)), "pinger");
                    }
                    return Behaviors.same();
                }).build();
            }), "MessageSystem", config);
        }
    }
}