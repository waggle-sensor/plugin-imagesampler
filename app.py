#!/usr/bin/env python3
# ANL:waggle-license
#  This file is part of the Waggle Platform.  Please see the file
#  LICENSE.waggle.txt for the legal details of the copyright and software
#  license.  For more details on the Waggle project, visit:
#           http://www.wa8.gl
# ANL:waggle-license
from datetime import datetime, timezone
import time
import os
import argparse
import re

import cv2

import waggle.plugin as plugin
from waggle.data import open_data_source

plugin.init()


def extract_topics(expr):
    topics = re.findall(r"\b[a-z]\w+", expr)
    for reserved in ['or', 'and']:
        while True:
            try:
                topics.remove(reserved)
            except ValueError:
                break
    return topics


def get_sample(stream, retry=5, timeout=5):
    with open_data_source(id=stream) as cam:
        for n in range(1, retry + 1):
            try:
                ts_ns, image = cam.get(timeout=timeout)
                return ts_ns, image
            except TimeoutError:
                print(f'get image timed out {n} time(s)', flush=True)
        return None, None


def run_on_event(args):
    print(f'starting image sampler whenever {args.condition} becomes valid', flush=True)
    topics = {}
    condition = args.condition.replace('.', '_')
    for t in extract_topics(condition):
        topics[t] = 0.
        plugin.subscribe(t.replace('_', '.'))

    cooldown = time.time()
    while True:
        msg = plugin.get()
        topics[msg.name.replace('.', '_')] = msg.value
        if time.time() < cooldown:
            time.sleep(0.1)
            continue

        if eval(condition, topics):
            print(f'{args.condition} is valid. getting image', flush=True)
            ts_ns, image = get_sample(args.stream)
            if image is None:
                raise Exception('failed to receive an image. halting the sampling...')

            if args.out_dir != "":
                # NOTE(YK) We lose nano seconds precision here
                dt = datetime.fromtimestamp(ts_ns / 1e9)
                path = os.path.join(args.out_dir,
                                    dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z.jpg'))
            else:
                path = "sample.jpg"

            print("writing image", flush=True)
            # NOTE: OpenCV assumes the image is BGR, but we have RGB (PyWaggle converts it into RGB)
            #       so we flip RGB to BGR to save the image in RGB
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            cv2.imwrite(path, image)

            print("uploading image", flush=True)
            plugin.upload_file(path)
            
            print(f'cooling down for {args.cooldown} seconds', flush=True)
            cooldown = time.time() + args.cooldown
        else:
            time.sleep(0.1)


def run_periodically(args):
    print(f"starting image sampler. will sample every {args.interval}s", flush=True)

    while True:
        time.sleep(args.interval)

        print("getting image", flush=True)
        
        ts_ns, image = get_sample(args.stream)
        if image is None:
            raise Exception('failed to receive an image. halting the sampling...')

        if args.out_dir != "":
            # NOTE(YK) We lose nano seconds precision here
            dt = datetime.fromtimestamp(ts_ns / 1e9)
            path = os.path.join(args.out_dir,
                                dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z.jpg'))
        else:
            path = "sample.jpg"

        print("writing image", flush=True)
        # NOTE: OpenCV assumes the image is BGR, but we have RGB (PyWaggle converts it into RGB)
        #       so we flip RGB to BGR to save the image in RGB
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(path, image)

        print("uploading image", flush=True)
        plugin.upload_file(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-stream', dest='stream',
        action='store', default="camera",
        help='ID or name of a stream, e.g. sample')
    parser.add_argument(
        '-out-dir', dest='out_dir',
        action='store', default="",
        help='Path to save images locally in %Y-%m-%dT%H:%M:%S%z.jpg format')
    parser.add_argument(
        '-interval', dest='interval',
        action='store', default=300, type=int,
        help='Inference interval in seconds')
    parser.add_argument(
        '-condition', dest='condition',
        action='store', default="", type=str,
        help='Triggering condition')
    parser.add_argument(
        '-cooldown', dest='cooldown',
        action='store', default=5, type=int,
        help='Cooldown in seconds after a trigger')

    args = parser.parse_args()
    if args.out_dir != "":
        os.makedirs(args.out_dir, exist_ok=True)

    if args.condition == "":
        run_periodically(args)
    else:
        run_on_event(args)
