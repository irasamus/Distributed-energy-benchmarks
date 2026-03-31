package com.energy;
import akka.actor.AbstractActor;
import akka.actor.ActorRef;
import java.io.Serializable;

public class SimpleActor extends AbstractActor {
    public static class Done implements Serializable {}
    private final ActorRef master;

    // The child now knows exactly who to tell "Done" to
    public SimpleActor(ActorRef master) {
        this.master = master;
    }

    @Override
    public void preStart() {
        master.tell(new Done(), getSelf());
        getContext().stop(getSelf());
    }

    @Override
    public Receive createReceive() { return receiveBuilder().build(); }
}