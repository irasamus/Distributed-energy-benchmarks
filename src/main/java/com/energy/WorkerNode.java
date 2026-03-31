package com.energy;

import akka.actor.*;
import com.typesafe.config.ConfigFactory;
import java.io.Serializable;

public class WorkerNode extends AbstractActor {
    // We explicitly pass the Master's ActorRef in the message
    public static class SpawnMe implements Serializable {
        public final ActorRef master;
        public SpawnMe(ActorRef master) { this.master = master; }
    }

    @Override
    public Receive createReceive() {
        return receiveBuilder()
            .match(SpawnMe.class, msg -> {
                // Pass the Master's address to the child
                getContext().actorOf(Props.create(SimpleActor.class, msg.master));
            })
            .build();
    }

    public static void main(String[] args) {
        String conf = "akka.actor.provider=remote\n" +
                      "akka.remote.artery.canonical.hostname=\"127.0.0.1\"\n" +
                      "akka.remote.artery.canonical.port=2552\n" +
                      "akka.actor.allow-java-serialization=on\n" +
                      "akka.remote.artery.advanced.outbound-message-queue-size=10000";
        
        ActorSystem sys = ActorSystem.create("RemoteSystem", ConfigFactory.parseString(conf));
        sys.actorOf(Props.create(WorkerNode.class), "factory");
        System.out.println("Worker Factory ready on Port 2552...");
    }
}