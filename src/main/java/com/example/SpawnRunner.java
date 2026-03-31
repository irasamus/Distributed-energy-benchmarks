package com.example;

import akka.actor.typed.*;
import akka.actor.typed.javadsl.*;
import akka.actor.typed.receptionist.*;
import com.typesafe.config.*;
import java.util.Set;

public class SpawnRunner {

    // 1. MESSAGES
    public interface MySerializable {}

    public static class SpawnRequest implements MySerializable {
        public ActorRef<ActorRef<String>> replyTo;
        public SpawnRequest() {} // Mandatory for Jackson
        public SpawnRequest(ActorRef<ActorRef<String>> replyTo) {
            this.replyTo = replyTo;
        }
    }

    public static final ServiceKey<SpawnRequest> SPAWNER_KEY = ServiceKey.create(SpawnRequest.class, "spawner-service");

    // 2. THE WORKER (To be spawned on Node B)
    public static Behavior<String> workerBehavior() {
        // We make the worker stop immediately after being spawned to save Node B's RAM
        return Behaviors.stopped();
    }

    // 3. THE SPAWNER (Running on Node B)
    public static Behavior<SpawnRequest> spawnerBehavior() {
        return Behaviors.setup(context -> {
            context.getSystem().receptionist().tell(Receptionist.register(SPAWNER_KEY, context.getSelf()));
            return Behaviors.receive(SpawnRequest.class)
                .onMessage(SpawnRequest.class, msg -> {
                    // Create the actor locally on Node B
                    ActorRef<String> child = context.spawn(workerBehavior(), "child-" + System.nanoTime());
                    // Send the reference back to Node A
                    msg.replyTo.tell(child);
                    return Behaviors.same();
                }).build();
        });
    }

    // 4. THE MASTER (Running on Node A - Sequential Logic)
    public static class Master extends AbstractBehavior<Object> {
        private final int targetCount;
        private int currentCount = 0;
        private ActorRef<SpawnRequest> remoteSpawner;
        private long startTime;

        public Master(ActorContext<Object> context, int targetCount) {
            super(context);
            this.targetCount = targetCount;
            // Discover Node B
            context.getSystem().receptionist().tell(Receptionist.subscribe(SPAWNER_KEY, context.getSelf().narrow()));
        }

        @Override
        public Receive<Object> createReceive() {
            return newReceiveBuilder()
                .onMessage(Receptionist.Listing.class, listing -> {
                    Set<ActorRef<SpawnRequest>> instances = listing.getServiceInstances(SPAWNER_KEY);
                    if (!instances.isEmpty() && remoteSpawner == null) {
                        this.remoteSpawner = instances.iterator().next();
                        this.startTime = System.currentTimeMillis();
                        System.out.println("LOG_START:" + startTime);
                        // Trigger the FIRST spawn
                        sendNextRequest();
                    }
                    return this;
                })
                .onMessage(ActorRef.class, ref -> {
                    // This is the reply from Node B. 
                    // It means the previous actor was spawned successfully.
                    currentCount++;
                    
                    if (currentCount % 5000 == 0) {
                        System.out.println("Spawned: " + currentCount + " / " + targetCount);
                    }

                    if (currentCount < targetCount) {
                        sendNextRequest();
                    } else {
                        long end = System.currentTimeMillis();
                        System.out.println("LOG_END:" + end);
                        System.out.println("Total time for " + targetCount + " sequential spawns: " + (end - startTime) + "ms");
                        return Behaviors.stopped();
                    }
                    return this;
                })
                .build();
        }

        private void sendNextRequest() {
            // We "narrow" the self reference so Node B knows where to send the ActorRef
            remoteSpawner.tell(new SpawnRequest((ActorRef) getContext().getSelf()));
        }
    }

    // 5. MAIN
    public static void main(String[] args) {
        String port = (args.length > 0) ? args[0] : "2551";
        // Change this number to whatever you need for your benchmark
        int totalToSpawn = 100000; 

        String configString = 
            "akka.actor.provider = cluster\n" +
            "akka.remote.artery.canonical.port = " + port + "\n" +
            "akka.remote.artery.canonical.hostname = \"127.0.0.1\"\n" +
            "akka.cluster.seed-nodes = [\"akka://SpawnSystem@127.0.0.1:2551\"]\n" +
            "akka.actor.serialization-bindings {\n" +
            "  \"com.example.SpawnRunner$MySerializable\" = jackson-cbor\n" +
            "}";

        Config config = ConfigFactory.parseString(configString).withFallback(ConfigFactory.load());

        if (port.equals("2551")) {
            ActorSystem.create(spawnerBehavior(), "SpawnSystem", config);
            System.out.println("Node B (Spawner) is UP.");
        } else {
            ActorSystem.create(Behaviors.setup(ctx -> new Master(ctx, totalToSpawn)), "SpawnSystem", config);
            System.out.println("Node A (Master) is UP.");
        }
    }
}