package main

import (
	"fmt"
	"math"
)

func Round(val float64, roundOn float64, places int) (newVal float64) {
	var round float64
	pow := math.Pow(10, float64(places))
	digit := pow * val
	_, div := math.Modf(digit)
	if div >= roundOn {
		round = math.Ceil(digit)
	} else {
		round = math.Floor(digit)
	}
	newVal = round / pow
	return
}

func readIn(transport *Transport) {
	pubsub, err := transport.Subscribe()
	failOnError(err)
	defer pubsub.Close()

	var stat StatSquidStat
	for {
		msg, err := pubsub.ReceiveMessage()
		if err != nil {
			panic(err)
		}
		stat.Unpack(msg.Payload)
		fmt.Println(stat.Names)
	}
}
